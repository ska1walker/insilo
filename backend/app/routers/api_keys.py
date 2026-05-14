"""CRUD for org-scoped API keys used by the external `/api/external/v1/*` endpoints.

The raw token is only ever exposed on creation (POST response). On every
subsequent read we expose just the metadata + the visible `key_prefix`
so the user can identify which key they're holding.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.auth_api import generate_api_key, normalize_scopes
from app.db import acquire

router = APIRouter(prefix="/api/v1", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    scopes: list[str] | None = None


class ApiKeyRead(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    created_at: str
    last_used_at: str | None
    revoked_at: str | None


class ApiKeyCreated(ApiKeyRead):
    """Initial create response — includes the full token exactly once."""

    token: str


def _row_to_read(row: dict[str, Any]) -> ApiKeyRead:
    return ApiKeyRead(
        id=str(row["id"]),
        name=row["name"],
        key_prefix=row["key_prefix"],
        scopes=list(row["scopes"] or []),
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
        last_used_at=row["last_used_at"].isoformat() if row["last_used_at"] else None,
        revoked_at=row["revoked_at"].isoformat() if row["revoked_at"] else None,
    )


@router.get("/api-keys", response_model=list[ApiKeyRead])
async def list_api_keys(
    user: CurrentUser = Depends(get_current_user),
) -> list[ApiKeyRead]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select id, name, key_prefix, scopes, created_at, last_used_at, revoked_at
            from public.api_keys
            where org_id = $1
            order by created_at desc
            """,
            user.org_id,
        )
    return [_row_to_read(dict(r)) for r in rows]


@router.post("/api-keys", status_code=201, response_model=ApiKeyCreated)
async def create_api_key(
    payload: ApiKeyCreate,
    user: CurrentUser = Depends(get_current_user),
) -> ApiKeyCreated:
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "name must not be empty")
    scopes = normalize_scopes(payload.scopes)

    token, prefix, hashed = generate_api_key()

    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into public.api_keys (
                org_id, name, key_prefix, key_hash, scopes, created_by
            )
            values ($1, $2, $3, $4, $5, $6)
            returning id, name, key_prefix, scopes, created_at, last_used_at, revoked_at
            """,
            user.org_id,
            name,
            prefix,
            hashed,
            scopes,
            user.user_id,
        )
    read = _row_to_read(dict(row))
    return ApiKeyCreated(**read.model_dump(), token=token)


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Soft-revoke: sets `revoked_at` so the key stops authenticating but
    the row stays around for audit purposes."""
    async with acquire() as conn:
        result = await conn.execute(
            """
            update public.api_keys
            set revoked_at = now()
            where id = $1 and org_id = $2 and revoked_at is null
            """,
            key_id,
            user.org_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "api key not found")
