"""Meeting CRUD + audio upload."""

import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.db import acquire
from app.errors import http_error
from app.storage import delete_object, get_presigned_url, upload_bytes
from app.tasks.notify import enqueue as enqueue_webhook
from app.tasks.transcribe import transcribe_meeting

_SPEAKER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

router = APIRouter(prefix="/api/v1", tags=["meetings"])


def _audio_key(org_id: UUID, meeting_id: UUID, mime_type: str) -> str:
    ext = "webm"
    if "mp4" in mime_type:
        ext = "m4a"
    elif "ogg" in mime_type:
        ext = "ogg"
    elif "wav" in mime_type:
        ext = "wav"
    return f"{org_id}/{meeting_id}.{ext}"


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
    async with acquire() as conn:
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


@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: UUID, user: CurrentUser = Depends(get_current_user)) -> dict:
    async with acquire() as conn:
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
                   t.name as template_name
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
    async with acquire() as conn:
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
        dto["summary"] = {
            "content": content,
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


@router.post("/recordings", status_code=201)
async def create_recording(
    audio: UploadFile = File(...),
    title: str = Form(...),
    duration_ms: int = Form(...),
    mime_type: str = Form(...),
    template_id: str | None = Form(default=None),
    language: str | None = Form(default=None),
    quick_mode: bool = Form(default=False),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
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

    blob = await audio.read()
    meeting_id = uuid4()
    key = _audio_key(user.org_id, meeting_id, mime_type)

    # Upload to MinIO first; only commit DB row on success.
    upload_bytes(key, blob, mime_type)

    duration_sec = max(1, duration_ms // 1000)

    # Quick-mode locks the template to the Schnellnotiz preset (a frontend
    # passing both `quick_mode=true` AND a template_id loses the picker —
    # we treat the quick flag as authoritative since the /idee UI has no
    # template selector anyway).
    tpl_uuid: UUID | None
    if quick_mode:
        tpl_uuid = _QUICK_NOTE_TEMPLATE_ID
    else:
        tpl_uuid = UUID(template_id) if template_id else None

    metadata: dict[str, Any] = {"mime_type": mime_type}
    if quick_mode:
        metadata["quick_mode"] = True

    async with acquire() as conn:
        # Validate template visibility if one was passed (otherwise the
        # summarize task falls back to the system default).
        if tpl_uuid is not None:
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

        row = await conn.fetchrow(
            """
            insert into public.meetings (
                id, org_id, created_by, title, status,
                duration_sec, audio_path, audio_size_bytes,
                language, template_id, metadata
            )
            values (
                $1, $2, $3, $4, 'queued',
                $5, $6, $7,
                $8, $9, $10::jsonb
            )
            returning id, title, recorded_at, duration_sec, audio_size_bytes,
                     audio_path, status, template_id,
                     metadata->>'mime_type' as audio_mime
            """,
            meeting_id,
            user.org_id,
            user.user_id,
            title,
            duration_sec,
            key,
            len(blob),
            db_language,
            tpl_uuid,
            json.dumps(metadata),
        )

    # Hand off transcription to the Celery worker. The HTTP response returns
    # immediately; the frontend polls status until it flips to "ready".
    transcribe_meeting.delay(str(meeting_id))
    enqueue_webhook(meeting_id, "meeting.created")

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

    async with acquire() as conn:
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
    async with acquire() as conn:
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

    async with acquire() as conn:
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
    async with acquire() as conn:
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
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            update public.meetings
            set deleted_at = now()
            where id = $1 and org_id = $2 and deleted_at is null
            returning audio_path
            """,
            meeting_id,
            user.org_id,
        )
    if row is None:
        raise http_error(404, "meeting.not_found")
    # Soft-delete in DB; also remove from object storage to reclaim space.
    if row["audio_path"]:
        try:
            delete_object(row["audio_path"])
        except Exception:
            # If object is already gone, don't fail the request.
            pass
    enqueue_webhook(meeting_id, "meeting.deleted")
