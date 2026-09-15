"""Meeting CRUD + audio upload."""

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import ablage, audit, relay_drop
from app.audioformat import MEDIENTYP, audio_endung
from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.db import acquire_as
from app.errors import http_error
from app.exports.markdown import sortieren
from app.storage import delete_object, get_presigned_url, upload_file
from app.tasks.notify import enqueue as enqueue_webhook
from app.tasks.transcribe import transcribe_meeting

log = logging.getLogger(__name__)

_SPEAKER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

router = APIRouter(prefix="/api/v1", tags=["meetings"])


def _audio_key(org_id: UUID, meeting_id: UUID, endung: str) -> str:
    return f"{org_id}/{meeting_id}.{endung}"


def _groesse(datei: BinaryIO) -> int:
    """Größe einer hochgeladenen Datei in Bytes.

    Starlette hat den Rumpf schon in eine Temporärdatei geschrieben;
    `UploadFile.size` ist nicht in jeder Fassung gesetzt, Ans-Ende-Springen
    schon.
    """
    datei.seek(0, 2)
    groesse = datei.tell()
    datei.seek(0)
    return groesse


def _meeting_row_to_dto(row, audio_url: str | None = None) -> dict:
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "created_at": row["recorded_at"].isoformat() if isinstance(row["recorded_at"], datetime) else row["recorded_at"],
        "duration_ms": (row["duration_sec"] or 0) * 1000,
        "mime_type": row["audio_mime"] or "audio/webm",
        "byte_size": row["audio_size_bytes"] or 0,
        "status": row["status"],
        "audio_url": audio_url,
        "tags": [],
    }


def _attach_tags(dtos: list[dict], tag_rows) -> None:
    """Hängt die per `(meeting_id) → tag` joined Rows an die DTOs."""
    by_meeting: dict[str, list[dict]] = {}
    for tr in tag_rows:
        mid = str(tr["meeting_id"])
        by_meeting.setdefault(mid, []).append(
            {"id": str(tr["id"]), "name": tr["name"], "color": tr["color"]}
        )
    for d in dtos:
        d["tags"] = by_meeting.get(d["id"], [])


@router.get("/meetings")
async def list_meetings(
    tag: list[UUID] = Query(default_factory=list),
    q: str | None = Query(default=None, max_length=120),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """List meetings of the user's org.

    Query params:
    - `tag` (repeatable): AND-filter — only meetings tagged with **all** given tag-IDs.
    - `q`: case-insensitive title substring search.
    """
    async with acquire_as(user.user_id) as conn:
        # Base query — join tag-count when AND-filter is set
        if tag:
            rows = await conn.fetch(
                """
                select m.id, m.title, m.recorded_at, m.duration_sec, m.audio_size_bytes,
                       m.audio_path, m.status, m.metadata->>'mime_type' as audio_mime
                from public.meetings m
                where m.org_id = $1
                  and m.deleted_at is null
                  and ($2::text is null or m.title ilike '%' || $2 || '%')
                  and (
                    select count(*) from public.meeting_tags mt
                    where mt.meeting_id = m.id and mt.tag_id = any($3::uuid[])
                  ) = $4
                order by m.recorded_at desc
                """,
                user.org_id,
                q,
                tag,
                len(tag),
            )
        else:
            rows = await conn.fetch(
                """
                select id, title, recorded_at, duration_sec, audio_size_bytes,
                       audio_path, status, metadata->>'mime_type' as audio_mime
                from public.meetings
                where org_id = $1
                  and deleted_at is null
                  and ($2::text is null or title ilike '%' || $2 || '%')
                order by recorded_at desc
                """,
                user.org_id,
                q,
            )

        dtos = [_meeting_row_to_dto(r) for r in rows]
        if not dtos:
            return dtos

        # In einem Schwung alle Tags aller geladenen Meetings holen.
        meeting_ids = [UUID(d["id"]) for d in dtos]
        tag_rows = await conn.fetch(
            """
            select mt.meeting_id, t.id, t.name, t.color
            from public.meeting_tags mt
            join public.tags t on t.id = mt.tag_id
            where mt.meeting_id = any($1::uuid[])
            order by t.name asc
            """,
            meeting_ids,
        )
        _attach_tags(dtos, tag_rows)

    return dtos


# Muss vor `/meetings/{meeting_id}` stehen: FastAPI prüft die Routen in
# Reihenfolge der Anmeldung, und `trash` würde sonst als Kennung gelesen
# und mit 422 abgelehnt — nicht durchgereicht.
@router.get("/meetings/trash")
async def list_trash(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Gelöschte Besprechungen, die noch zurückgeholt werden können.

    Bis v0.1.81 gab es diese Ansicht nicht — und auch nichts zu zeigen:
    das Löschen entfernte die Tonaufnahme sofort, die Frist galt nur für
    die Datenbankzeile.
    """
    async with acquire_as(user.user_id) as conn:
        frist = await conn.fetchval(
            "select trash_retention_days from public.orgs where id = $1",
            user.org_id,
        )
        rows = await conn.fetch(
            """
            select m.id, m.title, m.recorded_at, m.deleted_at, m.status,
                   m.duration_sec, m.audio_path, m.audio_deleted_at,
                   m.audio_size_bytes,
                   case when o.trash_retention_days > 0
                        then m.deleted_at + make_interval(days => o.trash_retention_days)
                   end as endgueltig_am
            from public.meetings m
            join public.orgs o on o.id = m.org_id
            where m.org_id = $1 and m.deleted_at is not null
            order by m.deleted_at desc
            """,
            user.org_id,
        )

    return {
        "frist_tage": frist or 0,
        "eintraege": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
                "deleted_at": r["deleted_at"].isoformat() if r["deleted_at"] else None,
                "endgueltig_am": (
                    r["endgueltig_am"].isoformat() if r["endgueltig_am"] else None
                ),
                "status": r["status"],
                "duration_ms": (r["duration_sec"] or 0) * 1000,
                "byte_size": r["audio_size_bytes"] or 0,
                "audio_vorhanden": bool(r["audio_path"]) and r["audio_deleted_at"] is None,
            }
            for r in rows
        ],
    }


@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: UUID, user: CurrentUser = Depends(get_current_user)) -> dict:
    async with acquire_as(user.user_id) as conn:
        row = await conn.fetchrow(
            """
            select m.id, m.title, m.recorded_at, m.duration_sec, m.audio_size_bytes,
                   m.audio_path, m.status, m.error_message, m.template_id,
                   m.metadata->>'mime_type' as audio_mime,
                   t.name as template_name
            from public.meetings m
            left join public.templates t on t.id = m.template_id
            where m.id = $1 and m.org_id = $2 and m.deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
        if row is None:
            raise http_error(404, "meeting.not_found")

        transcript_row = await conn.fetchrow(
            """
            select segments, speakers, full_text, language, whisper_model, word_count
            from public.transcripts
            where meeting_id = $1
            """,
            meeting_id,
        )

        summary_row = await conn.fetchrow(
            """
            select s.content, s.llm_model, s.generation_time_ms,
                   s.created_at, s.template_id, s.template_version,
                   t.name as template_name, t.output_schema
            from public.summaries s
            join public.templates t on t.id = s.template_id
            where s.meeting_id = $1 and s.is_current = true
            order by s.created_at desc
            limit 1
            """,
            meeting_id,
        )

    audio_url = get_presigned_url(row["audio_path"]) if row["audio_path"] else None
    dto = _meeting_row_to_dto(row, audio_url=audio_url)
    dto["error_message"] = row["error_message"]
    dto["template_id"] = str(row["template_id"]) if row["template_id"] else None
    dto["template_name"] = row["template_name"]

    # Tags zum Meeting
    async with acquire_as(user.user_id) as conn:
        tag_rows = await conn.fetch(
            """
            select t.id, t.name, t.color
            from public.meeting_tags mt
            join public.tags t on t.id = mt.tag_id
            where mt.meeting_id = $1
            order by t.name asc
            """,
            meeting_id,
        )
        dto["tags"] = [
            {"id": str(tr["id"]), "name": tr["name"], "color": tr["color"]}
            for tr in tag_rows
        ]

    if transcript_row is not None:
        segs = transcript_row["segments"]
        if isinstance(segs, str):
            segs = json.loads(segs)
        speakers_field = transcript_row["speakers"]
        if isinstance(speakers_field, str):
            speakers_field = json.loads(speakers_field)
        dto["transcript"] = {
            "segments": segs,
            "speakers": speakers_field or [],
            "full_text": transcript_row["full_text"],
            "language": transcript_row["language"],
            "whisper_model": transcript_row["whisper_model"],
            "word_count": transcript_row["word_count"],
        }

    if summary_row is not None:
        content = summary_row["content"]
        if isinstance(content, str):
            content = json.loads(content)
        schema = summary_row["output_schema"]
        if isinstance(schema, str):
            schema = json.loads(schema)

        # Welche Felder oben stehen, entscheidet `exports.markdown` — eine
        # Stelle für Ansicht und Datei. Die Oberfläche bekommt die fertige
        # Reihenfolge und braucht keine eigene Tabelle mit Feldnamen; sonst
        # liefen die beiden auseinander, sobald jemand eine Vorlage ändert.
        kopf, mehr = sortieren(content, schema)
        dto["summary"] = {
            "content": content,
            "kopf": kopf,
            "mehr": mehr,
            "llm_model": summary_row["llm_model"],
            "generation_time_ms": summary_row["generation_time_ms"],
            "created_at": summary_row["created_at"].isoformat() if summary_row["created_at"] else None,
            "template_id": str(summary_row["template_id"]),
            "template_name": summary_row["template_name"],
            "template_version": summary_row["template_version"],
        }

    return dto


_ALLOWED_RECORDING_LANGS: frozenset[str] = frozenset({"de", "en", "fr", "es", "it"})

# System-Template-ID for the Schauerfunktion / Quick-Capture flow.
# Defined in supabase/seed.sql. The /idee Car-Mode UI doesn't expose a
# template picker; quick-mode recordings always use this template.
_QUICK_NOTE_TEMPLATE_ID = UUID("00000000-0000-0000-0000-000000000005")


# Die Spalten, die eine angelegte Besprechung als Antwort braucht — beim
# Anlegen und bei einer erkannten Wiederholung dieselben.
_BESPRECHUNG_SPALTEN = """id, title, recorded_at, duration_sec, audio_size_bytes,
                 audio_path, status, template_id,
                 metadata->>'mime_type' as audio_mime"""

_FRUEHESTE_AUFNAHME = datetime(2000, 1, 1, tzinfo=UTC)


def _kennung(roh: str | None) -> str | None:
    """Die Kennung der Aufnahme aus dem Browser, oder `None`.

    Eine unbrauchbare Kennung lässt den Upload nicht scheitern — sie schützt
    dann nur nicht vor einer Wiederholung. Abgelehnt wird eine Aufnahme nie
    wegen eines Hilfsfelds.
    """
    if not roh or not roh.strip():
        return None
    try:
        return str(UUID(roh.strip()))
    except ValueError:
        return None


def _aufnahmezeit(roh: str | None, jetzt: datetime | None = None) -> datetime | None:
    """Wann aufgenommen wurde, wenn der Browser es weiß — sonst `None`.

    Bis 0.1.97 galt der Zeitpunkt des Hochladens. Eine erneut gesendete
    Aufnahme vom Vormittag stand dann am Nachmittag, eine eingespielte Datei
    vom Vormonat ganz oben. Angenommen werden ISO 8601 mit Zeitzone und
    Millisekunden seit 1970; alles vor 2000 oder mehr als einen Tag in der
    Zukunft (falsche Geräteuhr) fällt auf „jetzt" zurück.
    """
    if not roh or not roh.strip():
        return None
    text = roh.strip()
    try:
        if text.isdigit():
            zeit = datetime.fromtimestamp(int(text) / 1000, tz=UTC)
        else:
            zeit = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if zeit.tzinfo is None:
                return None
    except (ValueError, OverflowError, OSError):
        return None
    jetzt = jetzt or datetime.now(UTC)
    if zeit < _FRUEHESTE_AUFNAHME or zeit > jetzt + timedelta(days=1):
        return None
    return zeit


async def _schon_angelegt(user: CurrentUser, kennung: str) -> asyncpg.Record | None:
    # `metadata ? 'client_id'` steht nur da, damit Postgres den Teilindex aus
    # 0019 benutzt — ohne liest es die ganze Tabelle.
    async with acquire_as(user.user_id) as conn:
        return await conn.fetchrow(
            f"""
            select {_BESPRECHUNG_SPALTEN}, deleted_at
            from public.meetings
            where org_id = $1 and metadata ? 'client_id' and metadata->>'client_id' = $2
            limit 1
            """,
            user.org_id,
            kennung,
        )


def _wiederholung(request: Request, row: asyncpg.Record) -> JSONResponse:
    """Dieselbe Aufnahme kam ein zweites Mal: die vorhandene Besprechung.

    200 statt 201 — angelegt wurde nichts. Keine zweite Transkription, kein
    zweiter Webhook; im Protokoll steht der Aufruf mit dem Vermerk.

    Liegt sie im Papierkorb, 409: der Browser behält seine Sicherung (bei
    200 löschte er sie und landete auf einer Seite, die es nicht gibt), und
    der Text sagt, wo sie ist.
    """
    if row["deleted_at"] is not None:
        raise http_error(409, "meeting.recording_in_trash", titel=row["title"])
    audit.ergaenze(
        request.scope,
        kennung=row["id"],
        zusatz={"titel": row["title"], "wiederholung": True},
    )
    return JSONResponse(
        status_code=200,
        content=_meeting_row_to_dto(row, audio_url=get_presigned_url(row["audio_path"])),
    )


def _entfernen(key: str) -> None:
    try:
        delete_object(key)
    except Exception:
        log.exception("could not remove audio %s", key)


@router.post("/recordings", status_code=201, response_model=None)
async def create_recording(
    request: Request,
    audio: UploadFile = File(...),
    title: str = Form(...),
    duration_ms: int = Form(...),
    mime_type: str = Form(...),
    template_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
    quick_mode: bool = Form(default=False),
    client_id: str | None = Form(default=None),
    recorded_at: str | None = Form(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict | JSONResponse:
    # Normalize the language input:
    #   - missing / "" / "auto" → NULL (faster-whisper auto-detects)
    #   - "de"/"en"/"fr"/"es"/"it" → stored verbatim
    #   - anything else → 400
    db_language: str | None
    raw_lang = (language or "").strip().lower()
    if raw_lang in ("", "auto"):
        db_language = None
    elif raw_lang in _ALLOWED_RECORDING_LANGS:
        db_language = raw_lang
    else:
        raise http_error(400, "meeting.invalid_language", lang=raw_lang)

    # Erst alles prüfen, dann schreiben. Bis 0.1.96 lag die Datei schon in
    # der Ablage, bevor die Vorlage geprüft war — eine 400 ließ sie verwaist
    # zurück, und `audio.read()` hielt sie dafür ganz im Speicher.
    groesse = _groesse(audio.file)
    if groesse > settings.max_upload_mb * 1024 * 1024:
        raise http_error(413, "meeting.audio_too_large", max_mb=settings.max_upload_mb)

    # Dieselbe Aufnahme schon angelegt? Dann nichts schreiben — die Antwort
    # auf den ersten Versuch ist nur nicht beim Browser angekommen.
    kennung = _kennung(client_id)
    if kennung is not None:
        vorhanden = await _schon_angelegt(user, kennung)
        if vorhanden is not None:
            return _wiederholung(request, vorhanden)
    aufnahmezeit = _aufnahmezeit(recorded_at)

    endung = audio_endung(mime_type, audio.filename)
    # Ohne verwertbaren Typ (manche Dateiauswahl liefert keinen) gilt der,
    # der zur Endung passt — sonst spielt ihn der Browser später nicht ab.
    if not mime_type.strip() or mime_type.strip() == "application/octet-stream":
        mime_type = MEDIENTYP[endung]
    meeting_id = uuid4()
    key = _audio_key(user.org_id, meeting_id, endung)

    duration_sec = max(1, duration_ms // 1000)

    # Quick-mode locks the template to the Schnellnotiz preset (a frontend
    # passing both `quick_mode=true` AND a template_id loses the picker —
    # we treat the quick flag as authoritative since the /idee UI has no
    # template selector anyway).
    tpl_uuid: UUID | None
    if quick_mode:
        tpl_uuid = _QUICK_NOTE_TEMPLATE_ID
    elif template_id:
        try:
            tpl_uuid = UUID(template_id)
        except ValueError:
            raise http_error(400, "template.not_available") from None
    else:
        tpl_uuid = None

    metadata: dict[str, Any] = {"mime_type": mime_type}
    if quick_mode:
        metadata["quick_mode"] = True
    if kennung is not None:
        metadata["client_id"] = kennung

    # Validate template visibility if one was passed (otherwise the
    # summarize task falls back to the system default).
    if tpl_uuid is not None:
        async with acquire_as(user.user_id) as conn:
            allowed = await conn.fetchval(
                """
                select 1 from public.templates
                where id = $1
                  and is_active = true
                  and (is_system = true or org_id = $2)
                """,
                tpl_uuid,
                user.org_id,
            )
        if not allowed:
            raise http_error(400, "template.not_available")

    try:
        await run_in_threadpool(upload_file, key, audio.file, mime_type)
        async with acquire_as(user.user_id) as conn:
            row = await conn.fetchrow(
                f"""
                insert into public.meetings (
                    id, org_id, created_by, title, status,
                    duration_sec, audio_path, audio_size_bytes,
                    language, template_id, metadata, recorded_at
                )
                values (
                    $1, $2, $3, $4, 'queued',
                    $5, $6, $7,
                    $8, $9, $10::jsonb, coalesce($11::timestamptz, now())
                )
                returning {_BESPRECHUNG_SPALTEN}
                """,
                meeting_id,
                user.org_id,
                user.user_id,
                title,
                duration_sec,
                key,
                groesse,
                db_language,
                tpl_uuid,
                json.dumps(metadata),
                aufnahmezeit,
            )
    except asyncpg.UniqueViolationError:
        # Zwei Wiederholungen gleichzeitig: beide kamen an der Prüfung oben
        # vorbei, der Index (0019) lässt nur eine Zeile zu.
        _entfernen(key)
        vorhanden = await _schon_angelegt(user, kennung) if kennung else None
        if vorhanden is None:
            raise
        return _wiederholung(request, vorhanden)
    except Exception:
        # Ohne Zeile gehört die Datei niemandem; der Aufräumlauf fände sie
        # nie, weil er von den Zeilen aus sucht. Das gilt auch für eine
        # halb geschriebene Datei (Platte voll). Nur `Exception`: bricht die
        # Anfrage während des COMMIT ab, kann die Zeile schon stehen — dann
        # ist eine übrig gebliebene Datei das kleinere Übel als eine
        # Besprechung ohne Ton.
        _entfernen(key)
        raise

    # Hand off transcription to the Celery worker. The HTTP response returns
    # immediately; the frontend polls status until it flips to "ready".
    try:
        transcribe_meeting.delay(str(meeting_id))
    except Exception:
        # Die Zeile steht schon. Eine 500 hier ließe den Browser erneut
        # senden — und seit 0.1.98 bekäme er dann diese Besprechung zurück,
        # die ewig „in Warteschlange" stünde. Also als fehlgeschlagen
        # markieren: sichtbar, und „Neu verarbeiten" reiht sie wieder ein.
        log.exception("could not queue transcription for %s", meeting_id)
        async with acquire_as(user.user_id) as conn:
            await conn.execute(
                """
                update public.meetings
                set status = 'failed', error_message = $2, updated_at = now()
                where id = $1
                """,
                meeting_id,
                "Transkription konnte nicht gestartet werden (Warteschlange nicht erreichbar).",
            )
    enqueue_webhook(meeting_id, "meeting.created")

    # Die Besprechung ist der Gegenstand, um den es bei einer Rückfrage
    # geht — ihre Kennung entsteht aber erst hier, nicht im Pfad.
    audit.ergaenze(request.scope, kennung=row["id"], zusatz={"titel": row["title"]})
    return _meeting_row_to_dto(row, audio_url=get_presigned_url(key))


class SpeakerEntry(BaseModel):
    id: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=120)


class SpeakerAssignment(BaseModel):
    """Replace the speakers roster + per-segment speaker assignments.

    `speakers` is the canonical list (id + display name). `segments` maps
    segment index → speaker id (or null to clear). Unknown segment indices
    are ignored; ids that aren't in `speakers` are rejected.
    """

    speakers: list[SpeakerEntry] = Field(default_factory=list)
    segments: dict[str, str | None] = Field(default_factory=dict)


@router.put("/meetings/{meeting_id}/transcript/speakers")
async def update_transcript_speakers(
    meeting_id: UUID,
    payload: SpeakerAssignment,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    # Sanity: ids must be url-safe and unique.
    seen: set[str] = set()
    for s in payload.speakers:
        if not _SPEAKER_ID_RE.match(s.id):
            raise http_error(400, "meeting.invalid_speaker_id", sid=repr(s.id))
        if s.id in seen:
            raise http_error(400, "meeting.duplicate_speaker_id", sid=repr(s.id))
        seen.add(s.id)

    valid_ids = {s.id for s in payload.speakers}
    for idx, sid in payload.segments.items():
        if sid is not None and sid not in valid_ids:
            raise http_error(
                400,
                "meeting.unknown_speaker_ref",
                idx=idx,
                sid=repr(sid),
            )

    async with acquire_as(user.user_id) as conn:
        # Make sure the user owns the meeting.
        owned = await conn.fetchval(
            """
            select 1 from public.meetings
            where id = $1 and org_id = $2 and deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
        if not owned:
            raise http_error(404, "meeting.not_found")

        row = await conn.fetchrow(
            "select segments from public.transcripts where meeting_id = $1",
            meeting_id,
        )
        if row is None:
            raise http_error(409, "meeting.no_transcript")

        segs = row["segments"]
        if isinstance(segs, str):
            segs = json.loads(segs)
        if not isinstance(segs, list):
            raise HTTPException(500, "transcript.segments has unexpected shape")

        # Apply per-segment assignments. Keys come as strings from JSON.
        for k, sid in payload.segments.items():
            try:
                i = int(k)
            except ValueError:
                continue
            if 0 <= i < len(segs):
                segs[i]["speaker"] = sid

        speakers_payload = [s.model_dump() for s in payload.speakers]

        await conn.execute(
            """
            update public.transcripts
            set segments = $2::jsonb, speakers = $3::jsonb
            where meeting_id = $1
            """,
            meeting_id,
            json.dumps(segs),
            json.dumps(speakers_payload),
        )

    enqueue_webhook(meeting_id, "meeting.updated")
    return {"status": "ok", "speakers": speakers_payload, "segments": segs}


@router.post("/meetings/{meeting_id}/retry-summary", status_code=202)
async def retry_summary(
    meeting_id: UUID, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Re-queue summarization for a meeting whose summary failed or is stale.

    Useful after the user has configured a reachable LLM endpoint in
    Einstellungen — they don't want to re-record the meeting, just retry
    the summary step against the freshly-configured endpoint.
    """
    async with acquire_as(user.user_id) as conn:
        row = await conn.fetchrow(
            """
            select m.id, m.status, t.full_text
            from public.meetings m
            left join public.transcripts t on t.meeting_id = m.id
            where m.id = $1 and m.org_id = $2 and m.deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
        if row is None:
            raise http_error(404, "meeting.not_found")
        if not row["full_text"]:
            raise HTTPException(
                409, "no transcript yet — cannot summarize"
            )
        await conn.execute(
            """
            update public.meetings
            set status = 'summarizing', error_message = null, updated_at = now()
            where id = $1
            """,
            meeting_id,
        )

    # Send the task directly to Celery — `transcribe_meeting` would re-do
    # transcription, which is wasteful when only the summary needs retrying.
    from app.worker import celery_app
    celery_app.send_task("summarize_meeting", args=[str(meeting_id)])
    return {"status": "queued", "meeting_id": str(meeting_id)}


@router.post("/meetings/export-backfill", status_code=200)
async def export_backfill(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Alle fertigen Zusammenfassungen in das Relay-Verzeichnis schreiben.

    Einmaliger Nachzug für Besprechungen, die vor der Aktivierung von
    `MEETING_EXPORT_DIR` fertig waren. Ohne gesetztes Verzeichnis ist
    der Export deaktiviert — dann antwortet der Endpunkt mit 409.
    """
    if not (settings.meeting_export_dir or "").strip():
        raise HTTPException(409, "meeting export is disabled")
    async with acquire_as(user.user_id) as conn:
        # Nur Inhaber und Verwaltende. Der Aufruf legt die
        # Zusammenfassungen **aller** Besprechungen der Organisation in
        # einen Ordner, den andere Apps lesen — das ist keine Entscheidung,
        # die ein Mitglied oder eine Leserin für alle trifft. Dieselbe
        # Grenze wie beim Protokoll, das alle Vorgänge nur diesen beiden
        # Rollen zeigt.
        rolle = await conn.fetchval(
            "select role from public.user_org_roles where user_id = $1 and org_id = $2",
            user.user_id,
            user.org_id,
        )
        if rolle not in ("owner", "admin"):
            raise http_error(403, "meeting.export_forbidden")
        zeilen = await conn.fetch(
            """
            select id from public.meetings
            where deleted_at is null and status = 'ready'
            order by recorded_at desc
            limit 500
            """
        )
        geschrieben = 0
        for zeile in zeilen:
            if await relay_drop.schreiben(conn, zeile["id"]):
                geschrieben += 1
    return {"geschrieben": geschrieben, "geprueft": len(zeilen)}


class MeetingPatch(BaseModel):
    """Partial update — only fields actually sent get modified."""

    title: str | None = Field(default=None, min_length=1, max_length=255)


@router.patch("/meetings/{meeting_id}")
async def patch_meeting(
    meeting_id: UUID,
    payload: MeetingPatch,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Update a meeting's editable metadata (currently: title)."""
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise http_error(400, "meeting.no_fields")

    async with acquire_as(user.user_id) as conn:
        existing = await conn.fetchrow(
            """
            select id from public.meetings
            where id = $1 and org_id = $2 and deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
        if existing is None:
            raise http_error(404, "meeting.not_found")

        if "title" in fields:
            await conn.execute(
                """
                update public.meetings
                set title = $2, updated_at = now()
                where id = $1
                """,
                meeting_id,
                fields["title"].strip(),
            )

    enqueue_webhook(meeting_id, "meeting.updated")
    return {"status": "ok", "meeting_id": str(meeting_id), "updated": list(fields.keys())}


class DispatchRequest(BaseModel):
    """Manual webhook dispatch — user-triggered, bypasses trigger_mode.

    `webhook_ids` is the list of webhook UUIDs to deliver to. Pass an
    empty list (or omit) to dispatch to *all* active webhooks of the
    org that subscribe to `meeting.ready` (regardless of trigger_mode).
    """

    webhook_ids: list[UUID] = Field(default_factory=list)


@router.post("/meetings/{meeting_id}/dispatch", status_code=202)
async def dispatch_meeting(
    meeting_id: UUID,
    payload: DispatchRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Manually send the meeting.ready event to selected webhooks.

    Use case: the user has manual-mode webhooks (Default in v0.1.39) and
    wants to decide per meeting whether the outbound push happens. This
    endpoint is what the "An externe Systeme senden"-Button calls.
    """
    async with acquire_as(user.user_id) as conn:
        meeting = await conn.fetchrow(
            """
            select id, status from public.meetings
            where id = $1 and org_id = $2 and deleted_at is null
            """,
            meeting_id,
            user.org_id,
        )
    if meeting is None:
        raise http_error(404, "meeting.not_found")
    if meeting["status"] != "ready":
        raise HTTPException(
            409,
            f"meeting status is {meeting['status']!r} — only 'ready' meetings can be dispatched",
        )

    from app.tasks.notify import dispatch_manual

    result = await dispatch_manual(
        meeting_id,
        list(payload.webhook_ids) or None,
        user.org_id,
        event="meeting.ready",
    )
    return result


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: UUID, user: CurrentUser = Depends(get_current_user)
) -> None:
    """In den Papierkorb legen — die Tonaufnahme bleibt.

    Bis v0.1.81 entfernte dieser Endpunkt die Datei sofort. `deleted_at`
    war damit eine Frist auf eine Zeile, deren Inhalt schon weg war: wer
    versehentlich löschte, hatte die Aufnahme verloren, und CLAUDE.md
    versprach derweil „Soft-Delete + 30-Tage-Frist vor Hard-Delete".

    Die Datei entfernt jetzt `app.tasks.aufraeumen` nach Ablauf der Frist
    — oder sofort, wenn die Organisation `trash_retention_days = 0` führt.
    """
    async with acquire_as(user.user_id) as conn:
        row = await conn.fetchrow(
            """
            update public.meetings
            set deleted_at = now()
            where id = $1 and org_id = $2 and deleted_at is null
            returning id
            """,
            meeting_id,
            user.org_id,
        )
    if row is None:
        raise http_error(404, "meeting.not_found")
    enqueue_webhook(meeting_id, "meeting.deleted")


@router.post("/meetings/{meeting_id}/restore", status_code=204)
async def restore_meeting(
    meeting_id: UUID, user: CurrentUser = Depends(get_current_user)
) -> None:
    """Aus dem Papierkorb zurückholen.

    Wenn die Aufbewahrungsfrist die Tonaufnahme inzwischen entfernt hat,
    kommt die Besprechung ohne Datei zurück — Transkript und
    Zusammenfassung bleiben lesbar. Das ist der Zweck der getrennten
    Fristen.
    """
    row = None
    async with acquire_as(user.user_id) as conn:
        row = await conn.fetchrow(
            """
            update public.meetings
            set deleted_at = null
            where id = $1 and org_id = $2 and deleted_at is not null
            returning id
            """,
            meeting_id,
            user.org_id,
        )
    if row is None:
        raise http_error(404, "meeting.not_found")


@router.delete("/meetings/{meeting_id}/permanent", status_code=204)
async def purge_meeting(
    meeting_id: UUID, user: CurrentUser = Depends(get_current_user)
) -> None:
    """Endgültig entfernen — Zeile und Datei, ohne Frist.

    Nur aus dem Papierkorb heraus: was noch nicht gelöscht ist, kann hier
    nicht verschwinden. Transkript, Zusammenfassung, Abschnitte, Etiketten
    und Sprecher-Zuordnungen hängen mit `on delete cascade` daran.
    """
    async with acquire_as(user.user_id) as conn:
        row = await conn.fetchrow(
            """
            select audio_path from public.meetings
            where id = $1 and org_id = $2 and deleted_at is not null
            """,
            meeting_id,
            user.org_id,
        )
        if row is None:
            raise http_error(404, "meeting.not_found")

        # Erst die Datei, dann die Zeile: bleibt die Datei liegen, weil
        # der Speicher klemmt, zeigt die Zeile noch darauf und der
        # Aufräum-Job holt es nach. Andersherum wäre sie herrenlos —
        # genau der Zustand, der am 19.8. dreizehn Dateien gekostet hat.
        if row["audio_path"]:
            delete_object(row["audio_path"])

        # Und die beiden Markdown-Dateien daneben. Ohne das bliebe der
        # Gesprächsinhalt auf der Platte liegen, nachdem jemand
        # ausdrücklich „endgültig entfernen" gedrückt hat.
        ablage.entfernen(user.org_id, meeting_id)
        # Und die Kopie im gemeinsamen Relay-Verzeichnis.
        relay_drop.entfernen(meeting_id)

        await conn.execute(
            "delete from public.meetings where id = $1 and org_id = $2",
            meeting_id,
            user.org_id,
        )
