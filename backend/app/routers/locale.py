"""Locale-Settings: GET/PUT für UI-Sprache (User-Override + Org-Default).

GET liefert die aktuell aktive Locale (nach Resolution) plus die Quelle
(user/org/browser/default) und die unterstützten Sprachen. Das Frontend
zeigt damit „Aktuell: Deutsch (vom Browser erkannt)" als Hint.

PUT setzt entweder das User- oder das Org-Setting persistent. Leer-String
oder null im Body = "Override löschen" → fällt zurück auf die nächste
Resolution-Stufe.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.db import acquire
from app.locale import SUPPORTED, LocaleSource, resolve_locale

router = APIRouter(prefix="/api/v1", tags=["locale"])


class LocaleRead(BaseModel):
    active: str
    source: LocaleSource
    available: list[str]
    user_setting: str | None
    org_setting: str | None


class LocaleWrite(BaseModel):
    # null oder "" → Override löschen (fall through zur nächsten Stufe)
    locale: str | None = Field(default=None)
    scope: Literal["user", "org"] = "user"


@router.get("/locale", response_model=LocaleRead)
async def get_locale(
    user: CurrentUser = Depends(get_current_user),
    accept_language: str | None = Header(None, alias="Accept-Language"),
) -> LocaleRead:
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            select
              (select ui_locale from public.users        where id = $1) as user_locale,
              (select ui_locale from public.org_settings where org_id = $2) as org_locale
            """,
            user.user_id,
            user.org_id,
        )
    user_loc = (row["user_locale"] if row else None) or None
    org_loc = (row["org_locale"] if row else None) or None
    active, source = resolve_locale(
        user_locale=user_loc,
        org_locale=org_loc,
        accept_language=accept_language,
    )
    return LocaleRead(
        active=active,
        source=source,
        available=list(SUPPORTED),
        user_setting=user_loc,
        org_setting=org_loc,
    )


@router.put("/locale", status_code=204)
async def put_locale(
    payload: LocaleWrite,
    user: CurrentUser = Depends(get_current_user),
) -> None:
    raw = (payload.locale or "").strip()
    new_value: str | None
    if raw == "":
        new_value = None
    elif raw in SUPPORTED:
        new_value = raw
    else:
        raise HTTPException(
            400,
            f"unsupported locale: {raw!r}. Use one of {', '.join(SUPPORTED)} or null.",
        )

    async with acquire() as conn:
        if payload.scope == "user":
            await conn.execute(
                "update public.users set ui_locale = $2 where id = $1",
                user.user_id,
                new_value,
            )
        else:
            # org_settings-Row existiert ggf. noch nicht — upsert.
            await conn.execute(
                """
                insert into public.org_settings (org_id, ui_locale, updated_by)
                values ($1, $2, $3)
                on conflict (org_id) do update set
                  ui_locale = excluded.ui_locale,
                  updated_by = excluded.updated_by
                """,
                user.org_id,
                new_value,
                user.user_id,
            )
