"""Celery task: transcribe an uploaded meeting via the Whisper service."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from celery import shared_task

from app.config import settings
from app.storage import _client as _s3_client
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
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )


async def _do_transcribe(meeting_id: UUID) -> dict[str, Any]:
    """The real work — split out so we can run it inside asyncio.run()."""
    conn = await _connect()
    try:
        row = await conn.fetchrow(
            """
            select audio_path, metadata->>'mime_type' as mime
            from public.meetings
            where id = $1
            """,
            meeting_id,
        )
        if not row or not row["audio_path"]:
            return {"status": "skipped", "reason": "no audio_path"}

        await _set_status(conn, meeting_id, "transcribing")
    finally:
        await conn.close()

    # Pull audio out of MinIO. boto3 is sync; the bytes are small enough that
    # blocking the event loop briefly is fine.
    s3 = _s3_client()
    obj = s3.get_object(Bucket=settings.minio_bucket, Key=row["audio_path"])
    audio_bytes = obj["Body"].read()
    mime = row["mime"] or "audio/webm"
    log.info("transcribing meeting %s (%d bytes, %s)", meeting_id, len(audio_bytes), mime)

    # Call the Whisper service.
    transcribe_url = f"{settings.whisper_url}/transcribe"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 25)) as client:
        resp = await client.post(
            transcribe_url,
            files={"audio": ("recording.bin", audio_bytes, mime)},
            data={"language": settings.app_lang},
        )
        resp.raise_for_status()
        result = resp.json()

    segments = result["segments"]
    full_text = result["full_text"]

    # Persist the transcript and mark the meeting ready.
    conn = await _connect()
    try:
        async with conn.transaction():
            await conn.execute(
                """
                insert into public.transcripts (
                    meeting_id, segments, speakers, full_text,
                    language, whisper_model, word_count
                )
                values ($1, $2::jsonb, '[]'::jsonb, $3, $4, $5, $6)
                on conflict (meeting_id) do update set
                    segments = excluded.segments,
                    full_text = excluded.full_text,
                    language = excluded.language,
                    whisper_model = excluded.whisper_model,
                    word_count = excluded.word_count
                """,
                meeting_id,
                json.dumps(segments),
                full_text,
                result.get("language") or settings.app_lang,
                result.get("model") or "unknown",
                len(full_text.split()),
            )
            await _set_status(conn, meeting_id, "ready")
    finally:
        await conn.close()

    return {
        "status": "ok",
        "segments": len(segments),
        "language": result.get("language"),
        "duration": result.get("duration"),
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
        try:
            async def _mark_failed() -> None:
                conn = await _connect()
                try:
                    await _set_status(conn, mid, "failed", str(exc))
                finally:
                    await conn.close()

            asyncio.run(_mark_failed())
        except Exception:
            log.exception("could not flag meeting %s as failed", meeting_id)
        raise
