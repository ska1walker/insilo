"""Celery tasks: dispatch webhook deliveries for meeting lifecycle events.

Fires when a meeting transitions state (created / ready / failed /
updated / deleted). For `meeting.ready` events the payload includes the
full rendered Markdown — that's the moment downstream consumers (Duo,
OpenWebUI, custom integrations) actually want to file the meeting. For
every other event the payload is a minimal status update.

Task layout:

    notify_webhook(meeting_id, event)
        Orchestrator. Loads the payload once and fans out a
        per-subscriber `deliver_webhook` task. Each subscriber gets its
        own stable delivery_id.

    deliver_webhook(webhook_id, meeting_id, event, delivery_id, payload)
        Single-recipient dispatcher with retry. 5xx / timeout /
        connect-error trigger Celery retry with exponential backoff (max
        retries from settings). 4xx does NOT retry — that signals a
        client-side problem (wrong signature, bad URL handler) where
        retrying will only repeat the failure.

The `delivery_id` is identical across all retry attempts of the same
delivery so the receiver can deduplicate via `X-Insilo-Delivery-ID`.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
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


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _iso_or_none(v: Any) -> str | None:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _sign(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


# ─── Payload assembly ─────────────────────────────────────────────────


async def _load_meeting_payload(
    conn: asyncpg.Connection, meeting_id: UUID, event: str
) -> dict[str, Any] | None:
    """Build the payload for a meeting event.

    Returns the payload dict **without** an `id` field — the orchestrator
    assigns a per-subscriber delivery_id before dispatch so receivers can
    deduplicate. Returns None if the meeting row doesn't exist (hard-
    deleted or never existed). Soft-deleted meetings are still returned —
    the `meeting.deleted` event needs them.
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


# ─── deliver_webhook — single-recipient dispatcher with retry ──────────


async def _do_deliver(
    webhook_id: UUID,
    meeting_id: UUID,
    event: str,
    delivery_id: str,
    payload: dict[str, Any],
    attempt: int,
) -> tuple[bool, bool, int | None, str | None]:
    """Send one POST and record the result.

    Returns `(ok, should_retry, status_code, error_message)`.
    """
    conn = await _connect()
    try:
        wh = await conn.fetchrow(
            """
            select url, secret
            from public.org_webhooks
            where id = $1 and is_active = true
            """,
            webhook_id,
        )
        if wh is None:
            return False, False, None, "webhook gone or disabled"

        body_payload = {"id": delivery_id, **payload}
        body_bytes = json.dumps(body_payload, ensure_ascii=False).encode("utf-8")
        signature = _sign(wh["secret"], body_bytes)
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Insilo-Webhook/1.0",
            "X-Insilo-Event": event,
            "X-Insilo-Delivery-ID": delivery_id,
            "X-Insilo-Signature": signature,
        }

        status_code: int | None = None
        response_body: str | None = None
        error_message: str | None = None
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.webhook_default_timeout_sec)
            ) as client:
                resp = await client.post(wh["url"], content=body_bytes, headers=headers)
            status_code = resp.status_code
            response_body = resp.text[:_RESPONSE_BODY_CHARS]
        except httpx.TimeoutException:
            error_message = "timeout"
        except httpx.ConnectError as exc:
            error_message = f"connect: {exc.__class__.__name__}"
        except Exception as exc:  # noqa: BLE001
            error_message = f"{exc.__class__.__name__}: {exc}"

        ok = status_code is not None and 200 <= status_code < 300
        is_4xx = status_code is not None and 400 <= status_code < 500
        should_retry = (not ok) and (not is_4xx)

        async with conn.transaction():
            await conn.execute(
                """
                insert into public.webhook_deliveries (
                    webhook_id, meeting_id, event, status_code,
                    response_body, error_message, attempt
                )
                values ($1, $2, $3, $4, $5, $6, $7)
                """,
                webhook_id,
                meeting_id,
                event,
                status_code,
                response_body,
                error_message,
                attempt,
            )
            if ok:
                await conn.execute(
                    """
                    update public.org_webhooks
                    set last_success_at = now(),
                        last_failure_msg = null
                    where id = $1
                    """,
                    webhook_id,
                )
            else:
                await conn.execute(
                    """
                    update public.org_webhooks
                    set last_failure_at = now(),
                        last_failure_msg = $2
                    where id = $1
                    """,
                    webhook_id,
                    error_message or f"HTTP {status_code}",
                )

        log.info(
            "webhook dispatch · webhook=%s · event=%s · attempt=%s · status=%s · err=%s",
            webhook_id, event, attempt, status_code, error_message,
        )
        return ok, should_retry, status_code, error_message
    finally:
        await conn.close()


@shared_task(
    name="deliver_webhook",
    bind=True,
    max_retries=settings.webhook_max_retries,
)
def deliver_webhook(
    self,
    webhook_id: str,
    meeting_id: str,
    event: str,
    delivery_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Send one webhook payload to a single subscriber, with retry.

    Retries on 5xx / timeout / connect-error using exponential backoff
    (base * 3^retries). 4xx responses skip retry — they signal a
    client-side problem (wrong signature, bad URL handler) where retry
    will not help. `delivery_id` is stable across all retries so the
    receiver can deduplicate.
    """
    attempt = self.request.retries + 1
    try:
        ok, should_retry, status_code, error = asyncio.run(
            _do_deliver(
                UUID(webhook_id),
                UUID(meeting_id),
                event,
                delivery_id,
                payload,
                attempt,
            )
        )
    except Exception:
        log.exception("deliver_webhook crashed for webhook %s", webhook_id)
        raise

    if ok:
        return {
            "status": "ok",
            "webhook_id": webhook_id,
            "attempt": attempt,
            "status_code": status_code,
        }

    if not should_retry:
        return {
            "status": "failed",
            "webhook_id": webhook_id,
            "attempt": attempt,
            "status_code": status_code,
            "error": error,
            "retried": False,
        }

    if self.request.retries >= self.max_retries:
        log.warning(
            "webhook %s exhausted %s retries (last status=%s, err=%s)",
            webhook_id, self.max_retries, status_code, error,
        )
        return {
            "status": "exhausted",
            "webhook_id": webhook_id,
            "attempt": attempt,
            "status_code": status_code,
            "error": error,
        }

    countdown = settings.webhook_retry_base_delay_sec * (3 ** self.request.retries)
    raise self.retry(countdown=countdown)


# ─── notify_webhook — orchestrator ─────────────────────────────────────


async def _do_notify(meeting_id: UUID, event: str) -> dict[str, Any]:
    if event not in VALID_EVENTS:
        return {"status": "skipped", "reason": f"unknown event {event!r}"}

    conn = await _connect()
    try:
        org_row = await conn.fetchrow(
            """
            select org_id,
                   coalesce((metadata->>'quick_mode')::boolean, false) as quick_mode
            from public.meetings where id = $1
            """,
            meeting_id,
        )
        if org_row is None:
            return {"status": "skipped", "reason": "no meeting"}
        org_id = org_row["org_id"]
        quick_mode = org_row["quick_mode"]

        # Auto-Filter: bei meeting.ready werden manual-Webhooks
        # übersprungen — der User triggert sie per "An externe Systeme
        # senden"-Button auf der Meeting-Detail-Page. Alle anderen
        # Events (created/failed/updated/deleted) feuern immer
        # automatisch, unabhängig von trigger_mode.
        #
        # Ausnahme: Schauerfunktion / Quick-Capture (v0.1.50). Wenn die
        # Aufnahme im Car-Mode entstanden ist (metadata.quick_mode=true),
        # forcieren wir auch bei meeting.ready den Auto-Fan-Out — der
        # ganze UX-Punkt ist, dass nach "Stopp" nichts mehr geklickt
        # werden muss.
        if quick_mode:
            webhook_rows = await conn.fetch(
                """
                select id
                from public.org_webhooks
                where org_id = $1
                  and is_active = true
                  and $2 = any(events)
                """,
                org_id,
                event,
            )
        else:
            webhook_rows = await conn.fetch(
                """
                select id
                from public.org_webhooks
                where org_id = $1
                  and is_active = true
                  and $2 = any(events)
                  and ($2 <> 'meeting.ready' or trigger_mode = 'auto')
                """,
                org_id,
                event,
            )
        if not webhook_rows:
            return {"status": "ok", "fanout": 0, "reason": "no subscribers"}

        payload = await _load_meeting_payload(conn, meeting_id, event)
        if payload is None:
            return {"status": "skipped", "reason": "meeting vanished"}
    finally:
        await conn.close()

    from app.worker import celery_app as _app
    for wh in webhook_rows:
        delivery_id = uuid4().hex
        _app.send_task(
            "deliver_webhook",
            args=[
                str(wh["id"]),
                str(meeting_id),
                event,
                delivery_id,
                payload,
            ],
        )
    return {"status": "ok", "fanout": len(webhook_rows)}


@shared_task(name="notify_webhook")
def notify_webhook(meeting_id: str, event: str) -> dict[str, Any]:
    """Orchestrator: load payload once and fan out a `deliver_webhook`
    task per subscribed subscriber.
    """
    try:
        return asyncio.run(_do_notify(UUID(meeting_id), event))
    except Exception:
        log.exception("notify_webhook crashed for %s/%s", meeting_id, event)
        raise


# ─── Manual dispatch (user-triggered, bypasses trigger_mode filter) ────


async def dispatch_manual(
    meeting_id: UUID,
    webhook_ids: list[UUID] | None,
    org_id: UUID,
    event: str = "meeting.ready",
) -> dict[str, Any]:
    """User-triggered fan-out: send a meeting event to chosen webhooks.

    Unlike `_do_notify` this ignores `trigger_mode` and the event-
    subscription filter — the user explicitly picked these webhooks.
    Webhooks must still belong to `org_id` (security boundary) and be
    active (no point sending to a disabled receiver).

    `webhook_ids=None` means "all active webhooks of the org for this
    event" (respects subscription list, ignores trigger_mode).
    """
    if event not in VALID_EVENTS:
        return {"status": "skipped", "reason": f"unknown event {event!r}"}

    conn = await _connect()
    try:
        if webhook_ids:
            rows = await conn.fetch(
                """
                select id
                from public.org_webhooks
                where id = any($1::uuid[])
                  and org_id = $2
                  and is_active = true
                """,
                webhook_ids,
                org_id,
            )
        else:
            rows = await conn.fetch(
                """
                select id
                from public.org_webhooks
                where org_id = $1
                  and is_active = true
                  and $2 = any(events)
                """,
                org_id,
                event,
            )
        if not rows:
            return {"status": "ok", "fanout": 0, "reason": "no eligible webhooks"}

        payload = await _load_meeting_payload(conn, meeting_id, event)
        if payload is None:
            return {"status": "skipped", "reason": "meeting vanished"}
    finally:
        await conn.close()

    from app.worker import celery_app as _app
    for wh in rows:
        delivery_id = uuid4().hex
        _app.send_task(
            "deliver_webhook",
            args=[str(wh["id"]), str(meeting_id), event, delivery_id, payload],
        )
    return {"status": "ok", "fanout": len(rows)}


# ─── Public helper ─────────────────────────────────────────────────────


def enqueue(meeting_id: UUID | str, event: str) -> None:
    """Fire-and-forget enqueue from inside the FastAPI process.

    Importing Celery's `delay()` requires a configured broker; callers
    that don't already import `app.worker` should use this helper which
    keeps the Celery wiring local.
    """
    from app.worker import celery_app as _app
    _app.send_task("notify_webhook", args=[str(meeting_id), event])
