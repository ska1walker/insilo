"""Per-org settings: LLM endpoint + key + model.

The API never returns the raw `llm_api_key` — it returns `llm_api_key_set`
(bool) and the masked tail of the stored key. On PUT, an empty string means
"clear the override" (fall back to env), while a non-empty string overwrites.

If the client wants to keep the existing key untouched while changing other
fields, it sends `llm_api_key: null` (or omits the field).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.config import settings as env_settings
from app.db import acquire

router = APIRouter(prefix="/api/v1", tags=["settings"])


class SettingsRead(BaseModel):
    llm_base_url: str
    llm_api_key_set: bool
    llm_api_key_hint: str  # last 4 chars if set, else ""
    llm_model: str

    # Defaults from the deployment env — useful in the UI to show
    # "Aktuell aktiv: <env-default>" when the user has no override.
    defaults: dict[str, str]


class SettingsWrite(BaseModel):
    llm_base_url: str = Field(default="", max_length=500)
    # null = leave key untouched; "" = clear; anything else = overwrite.
    llm_api_key: str | None = None
    llm_model: str = Field(default="", max_length=200)


def _mask_hint(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 4:
        return "•" * len(key)
    return f"…{key[-4:]}"


def _row_to_read(row: dict[str, Any] | None) -> SettingsRead:
    base_url = (row or {}).get("llm_base_url", "") or ""
    api_key = (row or {}).get("llm_api_key", "") or ""
    model = (row or {}).get("llm_model", "") or ""
    return SettingsRead(
        llm_base_url=base_url,
        llm_api_key_set=bool(api_key),
        llm_api_key_hint=_mask_hint(api_key),
        llm_model=model,
        defaults={
            "llm_base_url": env_settings.llm_base_url,
            "llm_model": env_settings.llm_model,
        },
    )


@router.get("/settings", response_model=SettingsRead)
async def get_settings(user: CurrentUser = Depends(get_current_user)) -> SettingsRead:
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select llm_base_url, llm_api_key, llm_model
            from public.org_settings
            where org_id = $1
            """,
            user.org_id,
        )
    return _row_to_read(dict(row) if row else None)


@router.put("/settings", response_model=SettingsRead)
async def put_settings(
    payload: SettingsWrite,
    user: CurrentUser = Depends(get_current_user),
) -> SettingsRead:
    async with acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "select llm_api_key from public.org_settings where org_id = $1",
                user.org_id,
            )
            # null payload key → keep existing; otherwise replace (incl. "").
            api_key = (
                existing["llm_api_key"]
                if existing and payload.llm_api_key is None
                else (payload.llm_api_key or "")
            )

            row = await conn.fetchrow(
                """
                insert into public.org_settings (
                    org_id, llm_base_url, llm_api_key, llm_model, updated_by
                )
                values ($1, $2, $3, $4, $5)
                on conflict (org_id) do update set
                    llm_base_url = excluded.llm_base_url,
                    llm_api_key  = excluded.llm_api_key,
                    llm_model    = excluded.llm_model,
                    updated_by   = excluded.updated_by
                returning llm_base_url, llm_api_key, llm_model
                """,
                user.org_id,
                payload.llm_base_url.strip(),
                api_key,
                payload.llm_model.strip(),
                user.user_id,
            )
    return _row_to_read(dict(row))
