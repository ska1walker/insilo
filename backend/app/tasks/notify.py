"""Celery task: dispatch webhook deliveries for meeting lifecycle events.

Fires when a meeting transitions state (created / ready / failed / updated
/ deleted). Loads every active webhook subscribed to the given event for
the meeting's org, signs the payload with HMAC-SHA256(secret), POSTs with
a tight timeout, and records the outcome in `webhook_deliveries`.

For `meeting.ready` events the payload includes the full rendered
Markdown — that's the moment downstream consumers (Duo, OpenWebUI,
custom integrations) actually want to file the meeting. For every other
event the payload is a minimal status update.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import httpx
from celery import shared_task

from app.config import settings
from app.exports.markdown import render_meeting_markdown
from app.worker import celery_app  # noqa: F401  -- import side-effect: registers

log = logging.getLogger(__name__)

VALID_EVENTS = frozenset({
    "meeting.created",
    "meeting.ready",
    "meeting.failed",
    "meeting.deleted",
    "meeting.updated",
})

_RESPONSE_BODY_CHARS = 512


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )


async def _load_meeting_payload(
    conn: asyncpg.Connection, meeting_id: UUID, event: str
) -> dict[str, Any] | None:
    """Fetch everything we need to render the meeting for a webhook.

    Returns None if the meeting row doesn't exist at all (hard-deleted or
    never existed). Soft-deleted meetings are still returned — the
    `meeting.deleted` event needs them.
    """
    meeting_row = await conn.fetchrow(
        """
        select m.id, m.org_id, m.title, m.recorded_at, m.duration_sec,
               m.status, m.language, m.template_id, m.audio_size_bytes,
               m.error_message, m.deleted_at,
               t.name as template_name
        from public.meetings m
        left join public.templates t on t.id = m.template_id
        where m.id = $1
        """,
        meeting_id,
    )
    if meeting_row is None:
        return None

    include_full = event == "meeting.ready"

    transcript_row = None
    summary_row = None
    tag_rows: list[Any] = []
    if include_full:
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
            select s.content, s.llm_model, s.template_id, s.template_version,
                   s.created_at, t.name as template_name
            from public.summaries s
            join public.templates t on t.id = s.template_id
            where s.meeting_id = $1 and s.is_current = true
            order by s.created_at desc
            limit 1
            """,
            meeting_id,
        )
        tag_rows = await conn.fetch(
            """
            select t.name, t.color
            from public.meeting_tags mt
            join public.tags t on t.id = mt.tag_id
            where mt.meeting_id = $1
            order by t.name asc
            """,
            meeting_id,
        )

    meeting = dict(meeting_row)
    transcript = None
    if transcript_row is not None:
        segs = transcript_row["segments"]
        if isinstance(segs, str):
            segs = json.loads(segs)
        speakers = transcript_row["speakers"]
        if isinstance(speakers, str):
            speakers = json.loads(speakers)
        transcript = {
            "segments": segs or [],
            "speakers": speakers or [],
            "full_text": transcript_row["full_text"],
            "language": transcript_row["language"],
        }
    summary = None
    template_name = meeting.get("template_name")
    if summary_row is not None:
        content = summary_row["content"]
        if isinstance(content, str):
            content = json.loads(content)
        summary = {
            "content": content,
            "llm_model": summary_row["llm_model"],
        }
        template_name = summary_row["template_name"] or template_name
    tags = [{"name": r["name"], "color": r["color"]} for r in tag_rows]

    markdown: str | None = None
    if include_full:
        markdown = render_meeting_markdown(
            meeting=meeting,
            transcript=transcript,
            summary=summary,
            tags=tags,
            template_name=template_name,
            include_transcript=True,
        )

    payload: dict[str, Any] = {
        "id": str(uuid4()),  # delivery id, also sent as X-Insilo-Delivery-ID
        "event": event,
        "occurred_at": _iso_now(),
        "meeting": {
            "id": str(meeting["id"]),
            "org_id": str(meeting["org_id"]),
            "title": meeting["title"],
            "status": meeting["status"],
            "recorded_at": _iso_or_none(meeting["recorded_at"]),
            "duration_sec": meeting["duration_sec"],
            "language": meeting["language"],
            "template_id": (str(meeting["template_id"]) if meeting["template_id"] else None),
            "template_name": template_name,
            "error_message": meeting["error_message"],
            "deleted_at": _iso_or_none(meeting["deleted_at"]),
            "tags": [t["name"] for t in tags],
        },
    }
    if markdown:
        payload["markdown"] = markdown
    if summary and event == "meeting.ready":
        payload["summary"] = summary
    return payload


def _iso_now() -> str:
    from datetime import datetime
    return datetime.now(UTC).isoformat()


def _iso_or_none(v: Any) -> str | None:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _sign(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


async def _dispatch_one(
    conn: asyncpg.Connection,
    webhook: dict[str, Any],
    event: str,
    meeting_id: UUID,
    payload: dict[str, Any],
) -> None:
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    signature = _sign(webhook["secret"], body_bytes)
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "Insilo-Webhook/1.0",
        "X-Insilo-Event": event,
        "X-Insilo-Delivery-ID": payload["id"],
        "X-Insilo-Signature": signature,
    }

    status_code: int | None = None
    response_body: str | None = None
    error_message: str | None = None
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.webhook_default_timeout_sec)
        ) as client:
            resp = await client.post(webhook["url"], content=body_bytes, headers=headers)
        status_code = resp.status_code
        response_body = resp.text[:_RESPONSE_BODY_CHARS]
    except httpx.TimeoutException:
        error_message = "timeout"
    except httpx.ConnectError as exc:
        error_message = f"connect: {exc.__class__.__name__}"
    except Exception as exc:  # noqa: BLE001
        error_message = f"{exc.__class__.__name__}: {exc}"

    ok = status_code is not None and 200 <= status_code < 300

    async with conn.transaction():
        await conn.execute(
            """
            insert into public.webhook_deliveries (
                webhook_id, meeting_id, event, status_code,
                response_body, error_message, attempt
            )
            values ($1, $2, $3, $4, $5, $6, 1)
            """,
            webhook["id"],
            meeting_id,
            event,
            status_code,
            response_body,
            error_message,
        )
        if ok:
            await conn.execute(
                """
                update public.org_webhooks
                set last_success_at = now(),
                    last_failure_msg = null
                where id = $1
                """,
                webhook["id"],
            )
        else:
            await conn.execute(
                """
                update public.org_webhooks
                set last_failure_at = now(),
                    last_failure_msg = $2
                where id = $1
                """,
                webhook["id"],
                error_message or f"HTTP {status_code}",
            )

    log.info(
        "webhook dispatch · webhook=%s · event=%s · status=%s · err=%s",
        webhook["id"], event, status_code, error_message,
    )


async def _do_notify(meeting_id: UUID, event: str) -> dict[str, Any]:
    if event not in VALID_EVENTS:
        return {"status": "skipped", "reason": f"unknown event {event!r}"}

    conn = await _connect()
    try:
        # 1. Find the org
        org_row = await conn.fetchrow(
            "select org_id from public.meetings where id = $1",
            meeting_id,
        )
        if org_row is None:
            return {"status": "skipped", "reason": "no meeting"}
        org_id = org_row["org_id"]

        # 2. Find subscribed webhooks for this org
        webhook_rows = await conn.fetch(
            """
            select id, url, secret, events
            from public.org_webhooks
            where org_id = $1
              and is_active = true
              and $2 = any(events)
            """,
            org_id,
            event,
        )
        if not webhook_rows:
            return {"status": "ok", "delivered": 0, "reason": "no subscribers"}

        # 3. Build the payload once (it's identical across recipients)
        payload = await _load_meeting_payload(conn, meeting_id, event)
        if payload is None:
            return {"status": "skipped", "reason": "meeting vanished"}

        delivered = 0
        for wh in webhook_rows:
            try:
                await _dispatch_one(conn, dict(wh), event, meeting_id, payload)
                delivered += 1
            except Exception:
                log.exception("dispatch failed for webhook %s", wh["id"])
        return {"status": "ok", "delivered": delivered, "candidates": len(webhook_rows)}
    finally:
        await conn.close()


@shared_task(
    name="notify_webhook",
    bind=True,
    max_retries=settings.webhook_max_retries,
    default_retry_delay=30,
)
def notify_webhook(self, meeting_id: str, event: str) -> dict[str, Any]:  # noqa: ARG001
    """Sync Celery wrapper for the async notify pipeline."""
    try:
        return asyncio.run(_do_notify(UUID(meeting_id), event))
    except Exception:
        log.exception("notify_webhook crashed for %s/%s", meeting_id, event)
        raise


# ─── Public helper ─────────────────────────────────────────────────────

def enqueue(meeting_id: UUID | str, event: str) -> None:
    """Fire-and-forget enqueue from inside the FastAPI process.

    Importing Celery's `delay()` requires a configured broker; callers
    that don't already import `app.worker` should use this helper which
    keeps the Celery wiring local.
    """
    from app.worker import celery_app as _app
    _app.send_task("notify_webhook", args=[str(meeting_id), event])
