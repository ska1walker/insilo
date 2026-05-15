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
from app.llm_config import load_llm_config
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


def _wrap_user_prompt(transcript_text: str) -> str:
    return (
        "Hier folgt das Transkript der Besprechung. Analysiere es streng nach den "
        "Vorgaben des Systems und gib AUSSCHLIESSLICH ein JSON-Objekt zurück, das "
        "dem definierten Output-Schema entspricht.\n\n"
        f"=== TRANSKRIPT ===\n{transcript_text}\n=== ENDE TRANSKRIPT ==="
    )


def _format_transcript_for_llm(
    segments: list[dict[str, Any]] | None,
    speakers: list[dict[str, Any]] | None,
    fallback: str,
) -> str:
    """Bau ein speaker-annotiertes Transkript für die LLM-Eingabe.

    Hat das Transkript Speaker-Labels (Diarization ist gelaufen, der User
    hat Namen vergeben), wird daraus eine `[Name]: Text`-Zeile pro
    Segment — die LLM kann dann Beschlüsse Personen zuordnen.

    Ohne brauchbare Labels fallen wir auf den Plain-Text-Fallback zurück.
    """
    if not segments:
        return fallback
    name_by_id: dict[str, str] = {}
    for s in speakers or []:
        sid = s.get("id")
        name = s.get("name")
        if sid and name:
            name_by_id[sid] = name

    lines: list[str] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        sid = seg.get("speaker") or ""
        label = name_by_id.get(sid, sid or "Sprecher")
        lines.append(f"[{label}]: {text}")
    if not lines:
        return fallback
    return "\n".join(lines)


def _self_speaker_hint(speakers: list[dict[str, Any]] | None) -> str:
    """Optionaler Hinweis ans Modell: einer der Sprecher ist der Nutzer.

    Wenn das System weiß welcher Sprecher der User ist, kann die Summary
    Beschlüsse aus der Sie-Perspektive formulieren ("Sie hatten zugesagt
    …" statt "Kai hatte zugesagt …"). Greift nur wenn ein Org-Speaker
    mit is_self=true existiert und in diesem Meeting gesprochen hat.
    """
    if not speakers:
        return ""
    for s in speakers:
        if s.get("is_self") and s.get("name"):
            return (
                f"\n\nHinweis: Sprecher »{s['name']}« ist die Nutzerin/der Nutzer "
                "dieses Systems. Beschlüsse und Aufgaben dürfen — wo es natürlich "
                "wirkt — in zweiter Person formuliert werden (»Sie haben …«, "
                "»Ihnen obliegt …«) statt in dritter."
            )
    return ""


async def _do_summarize(meeting_id: UUID) -> dict[str, Any]:
    conn = await _connect()
    try:
        meeting = await conn.fetchrow(
            """
            select m.id, m.org_id, m.template_id,
                   t.full_text, t.word_count,
                   t.segments, t.speakers
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

        # Parse JSONB segments + speakers (asyncpg gives them back as strings).
        raw_segments = meeting["segments"]
        if isinstance(raw_segments, str):
            raw_segments = json.loads(raw_segments)
        raw_speakers = meeting["speakers"]
        if isinstance(raw_speakers, str):
            raw_speakers = json.loads(raw_speakers)
        # Annotate speakers with is_self by looking up the org-speaker row
        # they point to. transcripts.speakers entries with id="org_<uuid>"
        # carry an org_speaker_id we can resolve directly.
        speakers_enriched: list[dict[str, Any]] = []
        for s in (raw_speakers or []):
            entry = dict(s)
            org_sid = entry.get("org_speaker_id")
            if org_sid:
                row = await conn.fetchrow(
                    "select is_self from public.org_speakers where id = $1",
                    UUID(org_sid),
                )
                entry["is_self"] = bool(row and row["is_self"])
            speakers_enriched.append(entry)

        # Pick template: explicit on meeting, else the system default. Apply
        # the org's prompt customization (from /einstellungen) if present —
        # otherwise the seeded `system_prompt` is used.
        template_id = meeting["template_id"] or UUID(settings.default_template_id)
        template = await conn.fetchrow(
            """
            select t.id, t.version, t.output_schema,
                   coalesce(c.system_prompt, t.system_prompt) as system_prompt,
                   (c.template_id is not null) as is_customized
            from public.templates t
            left join public.template_customizations c
                on c.template_id = t.id and c.org_id = $2
            where t.id = $1
            """,
            template_id,
            meeting["org_id"],
        )
        if not template:
            return {"status": "skipped", "reason": "template missing"}
        if template["is_customized"]:
            log.info("using org-customized system prompt for template %s", template_id)

        # Per-org LLM endpoint/key/model (falls back to env defaults).
        llm = await load_llm_config(conn, meeting["org_id"])

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

    # Wenn das Transkript Sprecher-Labels hat, geben wir der LLM eine
    # speaker-annotierte Version statt nackten Fließtext — damit kann sie
    # Beschlüsse Personen zuordnen. Ohne Labels: identisch zu vorher.
    transcript_for_llm = _format_transcript_for_llm(
        raw_segments, speakers_enriched, fallback=meeting["full_text"]
    )

    # OpenAI-compatible JSON-mode (works for LiteLLM proxy and Ollama's
    # native /v1 endpoint). Schema enforcement is best-effort via prompt
    # instructions because not every backend supports structured outputs.
    payload = {
        "model": llm.model,
        "stream": False,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": template["system_prompt"]
                + _self_speaker_hint(speakers_enriched)
                + "\n\nAntwortformat: ein einziges JSON-Objekt, das diesem Schema entspricht:\n"
                + json.dumps(schema, ensure_ascii=False),
            },
            {"role": "user", "content": _wrap_user_prompt(transcript_for_llm)},
        ],
    }

    log.info(
        "summarize meeting %s · model=%s · template=%s",
        meeting_id, llm.model, template_id,
    )

    started = asyncio.get_event_loop().time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 10)) as client:
        resp = await client.post(
            f"{llm.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {llm.api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
    elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)

    choices = data.get("choices") or []
    content = (choices[0].get("message", {}) or {}).get("content", "") if choices else ""
    if not content.strip():
        raise RuntimeError("LLM returned empty content")

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
                llm.model,
                elapsed_ms,
            )
            await _set_status(conn, meeting_id, "ready")
    finally:
        await conn.close()

    # Fan out the embedding job. Status stays "ready" — embedding is a
    # background nice-to-have for RAG; it doesn't gate the user's view.
    from app.worker import celery_app as _app
    _app.send_task("embed_meeting", args=[str(meeting_id)])

    # Notify subscribers (Duo, OpenWebUI, …) that the meeting is ready.
    _app.send_task("notify_webhook", args=[str(meeting_id), "meeting.ready"])

    return {
        "status": "ok",
        "elapsed_ms": elapsed_ms,
        "model": llm.model,
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
        err_msg = f"summarize: {exc}"
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
