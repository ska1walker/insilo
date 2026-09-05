"""Celery task: transcribe an uploaded meeting via the Whisper service."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
import httpx
from celery import shared_task

from app.config import settings
from app.db import dienst_kontext
from app.speaker_matcher import (
    _to_pgvector,
    append_voiceprint_sample,
    load_org_voiceprints,
    match_centroids,
)
from app.storage import get_bytes as _storage_get_bytes
from app.stt_config import STTConfig, load_stt_config
from app.worker import celery_app  # noqa: F401  -- import side-effect: registers

log = logging.getLogger(__name__)


async def _set_status(
    conn: asyncpg.Connection, meeting_id: UUID, status: str, error: str | None = None
) -> None:
    await conn.execute(
        """
        update public.meetings
        set status = $2,
            error_message = $3,
            updated_at = now()
        where id = $1
        """,
        meeting_id,
        status,
        error,
    )


async def _connect() -> asyncpg.Connection:
    """Eigene Verbindung für diese Aufgabe — mit Dienst-Kontext.

    Hintergrundaufgaben haben keinen angemeldeten Nutzer. Unter der
    erzwungenen Zeilensicherheit aus Migration 0017 sähen sie ohne
    Kontext keine Zeile und könnten keine schreiben.
    """
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )
    await dienst_kontext(conn)
    return conn


@dataclass(frozen=True)
class Transkript:
    """Was ein Transkriptionsweg liefert — egal welcher.

    Beide Wege füllen dieselben Felder, damit der Rest der Pipeline nicht
    wissen muss, wer transkribiert hat.
    """

    segments: list[dict[str, Any]]
    full_text: str
    cluster_centroids: list[list[float]]
    language: str | None
    model: str
    duration: float | None
    # Woher der Text kommt — landet im Audit-Log und im Datenschutz-Nachweis.
    quelle: str  # "lokal" | "extern"


def _host_kurz(url: str) -> str:
    """Nur der Rechnername, für Meldungen an den Nutzer."""
    return urlsplit(url).hostname or url


def _dateiname(mime: str) -> str:
    """Dateiname mit passender Endung für den Upload.

    Einige STT-Server erkennen das Format an der Endung, nicht am
    MIME-Typ — mit "recording.bin" laufen sie ins Leere.
    """
    endung = {
        "webm": "webm", "mp4": "m4a", "ogg": "ogg",
        "wav": "wav", "mpeg": "mp3", "flac": "flac",
    }
    for kennung, e in endung.items():
        if kennung in mime:
            return f"recording.{e}"
    return "recording.webm"


async def _transkribieren_lokal(
    audio_bytes: bytes, mime: str, language: str | None,
) -> Transkript:
    """Der mitgelieferte Whisper-Dienst. Text und Sprecher in einem Aufruf.

    `language` wird weggelassen statt auf None gesetzt, damit
    faster-whisper selbst erkennt (sein Vorgabewert).
    """
    form_data: dict[str, str] = {}
    if language:
        form_data["language"] = language
    async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 25)) as client:
        resp = await client.post(
            f"{settings.whisper_url}/transcribe",
            files={"audio": ("recording.bin", audio_bytes, mime)},
            data=form_data,
        )
        resp.raise_for_status()
        result = resp.json()
    return Transkript(
        segments=result["segments"],
        full_text=result["full_text"],
        cluster_centroids=result.get("cluster_centroids") or [],
        language=result.get("language"),
        model=result.get("model") or "unknown",
        duration=result.get("duration"),
        quelle="lokal",
    )


async def _transkribieren_extern(
    audio_bytes: bytes, mime: str, language: str | None, stt: STTConfig,
) -> Transkript:
    """Externer OpenAI-kompatibler STT-Server, Sprecher weiterhin lokal.

    `response_format=verbose_json` liefert Segmente mit Zeiten; ohne sie
    gäbe es nur einen Textblock, und die Sprechertrennung hätte keine
    Grenzen, an denen sie ansetzen könnte. Antwortet der Endpunkt nur mit
    Text, arbeiten wir mit einem einzigen Segment weiter — lieber ein
    Transkript ohne Sprecher als gar keins.
    """
    # Die Modellkennung ist bei OpenAI-kompatiblen Endpunkten ein
    # Pflichtfeld — Speaches etwa antwortet ohne sie mit 422 und
    # "model: Field required". Das hier abzufangen ist ehrlicher, als den
    # Endpunkt einen Formfehler melden zu lassen: es fehlt eine Angabe,
    # der Dienst ist nicht kaputt.
    if not stt.model:
        raise RuntimeError(
            "Für die Spracherkennung fehlt die Modell-ID. Der eingetragene "
            f"Endpunkt ({_host_kurz(stt.base_url)}) verlangt sie bei jeder "
            "Anfrage. Sie steht unter Einstellungen › Spracherkennung; "
            "welche Kennungen der Endpunkt kennt, verrät sein /v1/models."
        )

    daten: dict[str, str] = {
        "response_format": "verbose_json",
        "model": stt.model,
    }
    if language:
        daten["language"] = language

    async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 25)) as client:
        resp = await client.post(
            f"{stt.base_url}/audio/transcriptions",
            # Dateiname mit echter Endung: manche Server leiten das Format
            # daraus ab statt aus dem MIME-Typ.
            files={"file": (_dateiname(mime), audio_bytes, mime)},
            data=daten,
            headers=stt.auth_header,
        )
        if resp.status_code >= 400:
            # Den Antwortkörper mitgeben. `raise_for_status()` allein
            # liefert nur "422 Unprocessable Entity", und der Nutzer steht
            # vor einer Sackgasse — dabei steht der Grund im Körper.
            raise RuntimeError(
                f"Der Spracherkennungs-Dienst antwortete mit HTTP "
                f"{resp.status_code}: {resp.text[:400]}"
            )
        roh = resp.json()

    volltext = (roh.get("text") or "").strip()
    segmente: list[dict[str, Any]] = [
        {
            "start": float(s.get("start", 0.0)),
            "end": float(s.get("end", 0.0)),
            "text": (s.get("text") or "").strip(),
            "speaker": None,
            "cluster_idx": None,
        }
        for s in (roh.get("segments") or [])
        if (s.get("text") or "").strip()
    ]
    if not segmente and volltext:
        dauer = float(roh.get("duration") or 0.0)
        segmente = [{
            "start": 0.0, "end": dauer, "text": volltext,
            "speaker": None, "cluster_idx": None,
        }]
    if not volltext:
        volltext = " ".join(s["text"] for s in segmente).strip()

    centroids = await _sprecher_ergaenzen(audio_bytes, mime, segmente)
    return Transkript(
        segments=segmente,
        full_text=volltext,
        cluster_centroids=centroids,
        language=roh.get("language") or language,
        model=stt.model or "extern",
        duration=float(roh["duration"]) if roh.get("duration") is not None else None,
        quelle="extern",
    )


async def _sprecher_ergaenzen(
    audio_bytes: bytes, mime: str, segmente: list[dict[str, Any]],
) -> list[list[float]]:
    """Sprecher zu fremd erzeugten Segmenten, über den lokalen Dienst.

    Schlägt das fehl, bleibt es beim Transkript ohne Sprechernamen — das
    ist ein Verlust an Komfort, kein Grund, die Besprechung scheitern zu
    lassen.
    """
    if not segmente:
        return []
    grenzen = json.dumps([[s["start"], s["end"]] for s in segmente])
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 10)) as client:
            resp = await client.post(
                f"{settings.whisper_url}/diarize",
                files={"audio": ("recording.bin", audio_bytes, mime)},
                data={"segments": grenzen},
            )
            resp.raise_for_status()
            d = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("speaker separation unavailable, continuing without: %s", exc)
        return []

    for seg, sprecher, cidx in zip(
        segmente, d.get("speakers") or [], d.get("cluster_indices") or [],
        strict=False,
    ):
        seg["speaker"] = sprecher
        seg["cluster_idx"] = cidx
    return d.get("cluster_centroids") or []


async def _do_transcribe(meeting_id: UUID) -> dict[str, Any]:
    """The real work — split out so we can run it inside asyncio.run()."""
    conn = await _connect()
    try:
        row = await conn.fetchrow(
            """
            select audio_path, org_id, language,
                   metadata->>'mime_type' as mime
            from public.meetings
            where id = $1
            """,
            meeting_id,
        )
        if not row or not row["audio_path"]:
            return {"status": "skipped", "reason": "no audio_path"}
        org_id = row["org_id"]

        await _set_status(conn, meeting_id, "transcribing")
    finally:
        await conn.close()

    # Pull audio out of storage (MinIO or local FS depending on backend).
    # Either path is sync; the bytes are small enough that blocking the event
    # loop briefly is fine.
    audio_bytes = _storage_get_bytes(row["audio_path"])
    mime = row["mime"] or "audio/webm"
    requested_language = row["language"]  # NULL = auto-detect (caller's choice)
    log.info(
        "transcribing meeting %s (%d bytes, %s, language=%s)",
        meeting_id, len(audio_bytes), mime, requested_language or "auto",
    )

    # Zwei Wege, je nach Einrichtung: der mitgelieferte Dienst im eigenen
    # Namespace (Vorgabe, kein Audio verlässt die Box) oder ein
    # eingetragener OpenAI-kompatibler STT-Server. Beim zweiten Weg holen
    # wir den Text von dort und die Sprecher weiterhin hier — ein
    # OpenAI-STT kennt keine Sprecher.
    conn = await _connect()
    try:
        stt = await load_stt_config(conn, org_id)
    finally:
        await conn.close()

    if stt.eingerichtet:
        log.info("transcribing via external endpoint %s", stt.base_url)
        tr = await _transkribieren_extern(audio_bytes, mime, requested_language, stt)
    else:
        tr = await _transkribieren_lokal(audio_bytes, mime, requested_language)

    segments = tr.segments
    full_text = tr.full_text
    cluster_centroids = tr.cluster_centroids

    # ─── Org-Speaker-Matching ─────────────────────────────────────────
    # Wenn die Org bereits Voiceprints kennt, ordnen wir jeden Cluster-
    # Centroid dem ähnlichsten Org-Speaker zu (cosine ≥ Threshold).
    # speakers_payload ist die Liste, die in transcripts.speakers landet —
    # mit echten Namen wo zugeordnet, sonst weiterhin "SPEAKER_NN".
    conn = await _connect()
    try:
        rows, vp_matrix = await load_org_voiceprints(conn, org_id)
    finally:
        await conn.close()
    matches = match_centroids(cluster_centroids, rows, vp_matrix) if cluster_centroids else []

    # Pro Cluster ein Speaker-Eintrag — id zeigt entweder auf einen Org-
    # Speaker ("org_<uuid>") oder bleibt cluster-anonym ("cluster_<n>").
    speakers_payload: list[dict[str, Any]] = []
    for c_idx in range(len(cluster_centroids)):
        if c_idx < len(matches) and matches[c_idx].org_speaker_id is not None:
            m = matches[c_idx]
            speakers_payload.append({
                "id": f"org_{m.org_speaker_id}",
                "name": m.display_name,
                "org_speaker_id": str(m.org_speaker_id),
                "match_score": round(m.score, 4),
                "assignment": "auto",
            })
        else:
            score = matches[c_idx].score if c_idx < len(matches) else 0.0
            speakers_payload.append({
                "id": f"cluster_{c_idx}",
                "name": f"SPEAKER_{c_idx:02d}",
                "match_score": round(score, 4),
                "assignment": "pending",
            })

    # Patch segment.speaker so the IDs in transcripts.segments line up
    # with the canonical speaker list above.
    for seg in segments:
        c_idx = seg.get("cluster_idx")
        if c_idx is not None and 0 <= c_idx < len(speakers_payload):
            seg["speaker"] = speakers_payload[c_idx]["id"]

    # ─── Persist transcript + clusters + auto-match voiceprints ──────
    conn = await _connect()
    try:
        async with conn.transaction():
            await conn.execute(
                """
                insert into public.transcripts (
                    meeting_id, segments, speakers, full_text,
                    language, whisper_model, word_count
                )
                values ($1, $2::jsonb, $3::jsonb, $4, $5, $6, $7)
                on conflict (meeting_id) do update set
                    segments = excluded.segments,
                    speakers = excluded.speakers,
                    full_text = excluded.full_text,
                    language = excluded.language,
                    whisper_model = excluded.whisper_model,
                    word_count = excluded.word_count
                """,
                meeting_id,
                json.dumps(segments),
                json.dumps(speakers_payload),
                full_text,
                tr.language or settings.app_lang,
                tr.model,
                len(full_text.split()),
            )

            # Wipe any clusters from a previous transcribe (re-diarize case),
            # then persist the new cluster set.
            await conn.execute(
                "delete from public.meeting_speaker_clusters where meeting_id = $1",
                meeting_id,
            )
            for c_idx, centroid in enumerate(cluster_centroids):
                match = matches[c_idx] if c_idx < len(matches) else None
                await conn.execute(
                    """
                    insert into public.meeting_speaker_clusters (
                        meeting_id, cluster_idx, centroid,
                        org_speaker_id, match_score, assignment
                    )
                    values ($1, $2, $3::vector, $4, $5, $6)
                    """,
                    meeting_id,
                    c_idx,
                    _to_pgvector(centroid),
                    match.org_speaker_id if match else None,
                    match.score if match else None,
                    "auto" if (match and match.org_speaker_id) else "pending",
                )

            await _set_status(conn, meeting_id, "transcribed")

        # Feed auto-matched centroids back into the speakers' voiceprint
        # history — that's how voiceprints refine over time. We do this
        # outside the main transaction so a single bad sample doesn't
        # roll back the whole transcript.
        for c_idx, match in enumerate(matches):
            if match.org_speaker_id is None or c_idx >= len(cluster_centroids):
                continue
            try:
                await append_voiceprint_sample(
                    conn,
                    org_speaker_id=match.org_speaker_id,
                    meeting_id=meeting_id,
                    cluster_idx=c_idx,
                    embedding=cluster_centroids[c_idx],
                    source="auto-match",
                )
            except Exception:
                log.exception(
                    "auto-match voiceprint append failed for speaker %s",
                    match.org_speaker_id,
                )
    finally:
        await conn.close()

    # Hand off to the LLM summarizer. Use send_task to avoid a circular import.
    from app.worker import celery_app as _app
    _app.send_task("summarize_meeting", args=[str(meeting_id)])

    return {
        "status": "ok",
        "segments": len(segments),
        "language": tr.language,
        "duration": tr.duration,
    }


@shared_task(
    name="transcribe_meeting",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def transcribe_meeting(self, meeting_id: str) -> dict[str, Any]:  # noqa: ARG001 (bind=True)
    """Sync Celery wrapper. Drives the async pipeline via asyncio.run."""
    mid = UUID(meeting_id)
    try:
        return asyncio.run(_do_transcribe(mid))
    except Exception as exc:
        log.exception("transcribe_meeting failed for %s", meeting_id)
        # Best-effort: mark the meeting as failed so the UI can show it.
        err_msg = str(exc)
        try:
            async def _mark_failed() -> None:
                conn = await _connect()
                try:
                    await _set_status(conn, mid, "failed", err_msg)
                finally:
                    await conn.close()

            asyncio.run(_mark_failed())
            from app.worker import celery_app as _app
            _app.send_task("notify_webhook", args=[meeting_id, "meeting.failed"])
        except Exception:
            log.exception("could not flag meeting %s as failed", meeting_id)
        raise
