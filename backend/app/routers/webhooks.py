"""CRUD for outgoing webhooks + manual test-trigger + delivery history.

Webhook secrets are never returned to the client after creation — the
read endpoints expose only `has_secret: true`. To rotate, send a new
`secret` (or omit to keep) on PUT.

The `/test` endpoint synchronously POSTs a fixed test payload so the
user can verify reachability without recording a real meeting.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from app.auth import CurrentUser, get_current_user
from app.db import acquire
from app.tasks.notify import VALID_EVENTS

router = APIRouter(prefix="/api/v1", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: HttpUrl
    description: str = Field(default="", max_length=500)
    events: list[str] = Field(default_factory=lambda: ["meeting.ready"])
    is_active: bool = True
    # 'manual' (default) requires the user to click "An externe Systeme
    # senden" on each meeting before meeting.ready is fired. 'auto'
    # fires on every meeting once the summary is done.
    trigger_mode: str = Field(default="manual", pattern="^(manual|auto)$")
    # null → server-generated secret. Caller-supplied secrets must be
    # ≥16 chars so HMAC has reasonable strength.
    secret: str | None = Field(default=None, min_length=16, max_length=200)


class WebhookUpdate(BaseModel):
    url: HttpUrl | None = None
    description: str | None = Field(default=None, max_length=500)
    events: list[str] | None = None
    is_active: bool | None = None
    trigger_mode: str | None = Field(default=None, pattern="^(manual|auto)$")
    # null = keep existing; non-null = rotate.
    secret: str | None = Field(default=None, min_length=16, max_length=200)


class WebhookRead(BaseModel):
    id: str
    url: str
    description: str
    events: list[str]
    is_active: bool
    trigger_mode: str
    has_secret: bool
    created_at: str
    last_success_at: str | None
    last_failure_at: str | None
    last_failure_msg: str | None


class WebhookCreated(WebhookRead):
    """Initial create response — includes the secret exactly once."""

    secret: str


class DeliveryRead(BaseModel):
    id: str
    meeting_id: str | None
    event: str
    status_code: int | None
    response_body: str | None
    error_message: str | None
    attempt: int
    created_at: str


class TestResult(BaseModel):
    ok: bool
    status_code: int | None = None
    response_body: str | None = None
    error_message: str | None = None
    elapsed_ms: int | None = None


def _row_to_read(row: dict[str, Any]) -> WebhookRead:
    return WebhookRead(
        id=str(row["id"]),
        url=row["url"],
        description=row["description"] or "",
        events=list(row["events"] or []),
        is_active=bool(row["is_active"]),
        trigger_mode=row.get("trigger_mode") or "manual",
        has_secret=bool(row["secret"]),
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
        last_success_at=row["last_success_at"].isoformat() if row["last_success_at"] else None,
        last_failure_at=row["last_failure_at"].isoformat() if row["last_failure_at"] else None,
        last_failure_msg=row["last_failure_msg"],
    )


def _validate_events(events: list[str]) -> list[str]:
    if not events:
        raise HTTPException(400, "At least one event must be selected.")
    bad = [e for e in events if e not in VALID_EVENTS]
    if bad:
        raise HTTPException(400, f"Unknown events: {', '.join(bad)}")
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for e in events:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


@router.get("/webhooks", response_model=list[WebhookRead])
async def list_webhooks(user: CurrentUser = Depends(get_current_user)) -> list[WebhookRead]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select id, url, description, events, is_active, trigger_mode, secret,
                   created_at, last_success_at, last_failure_at, last_failure_msg
            from public.org_webhooks
            where org_id = $1
            order by created_at desc
            """,
            user.org_id,
        )
    return [_row_to_read(dict(r)) for r in rows]


@router.post("/webhooks", status_code=201, response_model=WebhookCreated)
async def create_webhook(
    payload: WebhookCreate,
    user: CurrentUser = Depends(get_current_user),
) -> WebhookCreated:
    events = _validate_events(payload.events)
    secret = payload.secret or secrets.token_urlsafe(32)

    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into public.org_webhooks (
                org_id, url, description, events, is_active,
                trigger_mode, secret, created_by
            )
            values ($1, $2, $3, $4, $5, $6, $7, $8)
            returning id, url, description, events, is_active, trigger_mode, secret,
                      created_at, last_success_at, last_failure_at, last_failure_msg
            """,
            user.org_id,
            str(payload.url),
            payload.description.strip(),
            events,
            payload.is_active,
            payload.trigger_mode,
            secret,
            user.user_id,
        )
    read = _row_to_read(dict(row))
    return WebhookCreated(**read.model_dump(), secret=secret)


@router.put("/webhooks/{webhook_id}", response_model=WebhookRead)
async def update_webhook(
    webhook_id: UUID,
    payload: WebhookUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> WebhookRead:
    events = _validate_events(payload.events) if payload.events is not None else None

    async with acquire() as conn:
        existing = await conn.fetchrow(
            "select id from public.org_webhooks where id = $1 and org_id = $2",
            webhook_id,
            user.org_id,
        )
        if existing is None:
            raise HTTPException(404, "webhook not found")

        row = await conn.fetchrow(
            """
            update public.org_webhooks set
                url          = coalesce($2, url),
                description  = coalesce($3, description),
                events       = coalesce($4, events),
                is_active    = coalesce($5, is_active),
                trigger_mode = coalesce($6, trigger_mode),
                secret       = coalesce($7, secret)
            where id = $1
            returning id, url, description, events, is_active, trigger_mode, secret,
                      created_at, last_success_at, last_failure_at, last_failure_msg
            """,
            webhook_id,
            str(payload.url) if payload.url is not None else None,
            payload.description.strip() if payload.description is not None else None,
            events,
            payload.is_active,
            payload.trigger_mode,
            payload.secret,
        )
    return _row_to_read(dict(row))


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    async with acquire() as conn:
        result = await conn.execute(
            "delete from public.org_webhooks where id = $1 and org_id = $2",
            webhook_id,
            user.org_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, "webhook not found")


@router.post("/webhooks/{webhook_id}/test", response_model=TestResult)
async def test_webhook(
    webhook_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> TestResult:
    """Synchronously POST a fixed test payload to the webhook target.

    Useful to verify reachability + signature handling without recording
    a meeting. The result is NOT written to `webhook_deliveries` — that
    table is reserved for real lifecycle events.
    """
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select url, secret
            from public.org_webhooks
            where id = $1 and org_id = $2
            """,
            webhook_id,
            user.org_id,
        )
        if row is None:
            raise HTTPException(404, "webhook not found")

    payload = {
        "id": secrets.token_urlsafe(16),
        "event": "test.ping",
        "occurred_at": datetime.now(UTC).isoformat(),
        "message": "Testlieferung von Insilo — alles in Ordnung.",
    }
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    signature = "sha256=" + hmac.new(
        row["secret"].encode("utf-8"), body_bytes, hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "Insilo-Webhook/1.0",
        "X-Insilo-Event": "test.ping",
        "X-Insilo-Delivery-ID": payload["id"],
        "X-Insilo-Signature": signature,
    }
    started = datetime.now(UTC)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(row["url"], content=body_bytes, headers=headers)
        elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        return TestResult(
            ok=200 <= resp.status_code < 300,
            status_code=resp.status_code,
            response_body=resp.text[:512],
            elapsed_ms=elapsed_ms,
        )
    except httpx.TimeoutException:
        return TestResult(ok=False, error_message="Zeitüberschreitung (10 s).")
    except httpx.ConnectError as exc:
        return TestResult(ok=False, error_message=f"Verbindung fehlgeschlagen: {exc.__class__.__name__}")
    except Exception as exc:  # noqa: BLE001
        return TestResult(ok=False, error_message=f"{exc.__class__.__name__}: {exc}")


@router.get("/webhooks/{webhook_id}/deliveries", response_model=list[DeliveryRead])
async def list_deliveries(
    webhook_id: UUID,
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
) -> list[DeliveryRead]:
    limit = max(1, min(limit, 200))
    async with acquire() as conn:
        owned = await conn.fetchval(
            "select 1 from public.org_webhooks where id = $1 and org_id = $2",
            webhook_id,
            user.org_id,
        )
        if not owned:
            raise HTTPException(404, "webhook not found")
        rows = await conn.fetch(
            """
            select id, meeting_id, event, status_code, response_body,
                   error_message, attempt, created_at
            from public.webhook_deliveries
            where webhook_id = $1
            order by created_at desc
            limit $2
            """,
            webhook_id,
            limit,
        )
    return [
        DeliveryRead(
            id=str(r["id"]),
            meeting_id=str(r["meeting_id"]) if r["meeting_id"] else None,
            event=r["event"],
            status_code=r["status_code"],
            response_body=r["response_body"],
            error_message=r["error_message"],
            attempt=r["attempt"],
            created_at=r["created_at"].isoformat() if r["created_at"] else "",
        )
        for r in rows
    ]
