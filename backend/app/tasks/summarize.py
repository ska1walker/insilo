"""Celery task: generate a structured summary of a transcribed meeting via Ollama."""

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
from app.worker import celery_app  # noqa: F401 -- side-effect: registers worker

log = logging.getLogger(__name__)


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )


async def _set_status(
    conn: asyncpg.Connection, meeting_id: UUID, status: str, error: str | None = None
) -> None:
    await conn.execute(
        """
        update public.meetings
        set status = $2, error_message = $3, updated_at = now()
        where id = $1
        """,
        meeting_id,
        status,
        error,
    )


def _wrap_user_prompt(full_text: str) -> str:
    return (
        "Hier folgt das Transkript der Besprechung. Analysiere es streng nach den "
        "Vorgaben des Systems und gib AUSSCHLIESSLICH ein JSON-Objekt zurück, das "
        "dem definierten Output-Schema entspricht.\n\n"
        f"=== TRANSKRIPT ===\n{full_text}\n=== ENDE TRANSKRIPT ==="
    )


async def _do_summarize(meeting_id: UUID) -> dict[str, Any]:
    conn = await _connect()
    try:
        meeting = await conn.fetchrow(
            """
            select m.id, m.template_id,
                   t.full_text, t.word_count
            from public.meetings m
            left join public.transcripts t on t.meeting_id = m.id
            where m.id = $1 and m.deleted_at is null
            """,
            meeting_id,
        )
        if not meeting:
            return {"status": "skipped", "reason": "no meeting"}
        if not meeting["full_text"]:
            return {"status": "skipped", "reason": "no transcript"}

        # Pick template: explicit on meeting, else the system default.
        template_id = meeting["template_id"] or UUID(settings.default_template_id)
        template = await conn.fetchrow(
            """
            select id, version, system_prompt, output_schema
            from public.templates
            where id = $1
            """,
            template_id,
        )
        if not template:
            return {"status": "skipped", "reason": "template missing"}

        await _set_status(conn, meeting_id, "summarizing")
    finally:
        await conn.close()

    # Build the LLM request. Ollama supports `format` as either "json" (loose)
    # or a JSON-Schema object (strict, >=0.5). We pass the schema for stricter
    # adherence — falling back to "json" if the model can't keep up.
    schema = (
        template["output_schema"]
        if isinstance(template["output_schema"], dict)
        else json.loads(template["output_schema"])
    )

    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": schema,
        "options": {
            "temperature": 0.2,  # protocols want determinism, not creativity
            "num_ctx": 8192,
        },
        "messages": [
            {"role": "system", "content": template["system_prompt"]},
            {"role": "user", "content": _wrap_user_prompt(meeting["full_text"])},
        ],
    }

    log.info(
        "summarize meeting %s · model=%s · template=%s",
        meeting_id, settings.ollama_model, template_id,
    )

    started = asyncio.get_event_loop().time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 10)) as client:
        resp = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)

    content = (data.get("message") or {}).get("content") or ""
    if not content.strip():
        raise RuntimeError("ollama returned empty content")

    try:
        structured = json.loads(content)
    except json.JSONDecodeError as exc:
        log.error("ollama returned non-JSON content: %r", content[:500])
        raise RuntimeError(f"ollama returned non-JSON: {exc}") from exc

    conn = await _connect()
    try:
        async with conn.transaction():
            # Older summaries lose their current flag.
            await conn.execute(
                "update public.summaries set is_current = false where meeting_id = $1",
                meeting_id,
            )
            await conn.execute(
                """
                insert into public.summaries (
                    meeting_id, template_id, template_version,
                    content, llm_model, generation_time_ms, is_current
                )
                values ($1, $2, $3, $4::jsonb, $5, $6, true)
                """,
                meeting_id,
                template["id"],
                template["version"],
                json.dumps(structured),
                settings.ollama_model,
                elapsed_ms,
            )
            await _set_status(conn, meeting_id, "ready")
    finally:
        await conn.close()

    return {
        "status": "ok",
        "elapsed_ms": elapsed_ms,
        "model": settings.ollama_model,
    }


@shared_task(
    name="summarize_meeting",
    bind=True,
    max_retries=1,
    default_retry_delay=15,
)
def summarize_meeting(self, meeting_id: str) -> dict[str, Any]:  # noqa: ARG001
    mid = UUID(meeting_id)
    try:
        return asyncio.run(_do_summarize(mid))
    except Exception as exc:
        log.exception("summarize_meeting failed for %s", meeting_id)
        try:
            async def _mark_failed() -> None:
                conn = await _connect()
                try:
                    await _set_status(conn, mid, "failed", f"summarize: {exc}")
                finally:
                    await conn.close()

            asyncio.run(_mark_failed())
        except Exception:
            log.exception("could not flag meeting %s as failed", meeting_id)
        raise
