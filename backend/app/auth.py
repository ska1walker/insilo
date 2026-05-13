"""Olares-Header-based identity + auto-provisioning of dev users."""

from uuid import UUID

from fastapi import Header, HTTPException
from pydantic import BaseModel

from app.db import acquire


class CurrentUser(BaseModel):
    """User-Identität aus Olares-Authelia-Header (X-Bfl-User) + DB-Mapping."""

    olares_username: str
    user_id: UUID
    org_id: UUID
    display_name: str | None = None


async def _ensure_user_and_org(olares_username: str) -> CurrentUser:
    """
    Auf der echten Olares-Box legt das Admin-Onboarding User + Org an.
    Für lokale Dev provisionieren wir hier automatisch, sodass der erste
    Request einer neuen X-Bfl-User-Identität nicht fehlschlägt.
    """
    async with acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                insert into public.users (olares_username, display_name)
                values ($1, $1)
                on conflict (olares_username) do update set last_seen_at = now()
                returning id, display_name
                """,
                olares_username,
            )
            user_id = row["id"]
            display_name = row["display_name"]

            org = await conn.fetchrow(
                """
                select o.id
                from public.orgs o
                join public.user_org_roles r on r.org_id = o.id
                where r.user_id = $1 and o.deleted_at is null
                limit 1
                """,
                user_id,
            )

            if org is None:
                org = await conn.fetchrow(
                    """
                    insert into public.orgs (name, slug)
                    values ($1, $2)
                    returning id
                    """,
                    f"{olares_username}'s Organisation",
                    f"org-{olares_username}",
                )
                await conn.execute(
                    """
                    insert into public.user_org_roles (user_id, org_id, role)
                    values ($1, $2, 'owner')
                    on conflict (user_id, org_id) do nothing
                    """,
                    user_id,
                    org["id"],
                )

            return CurrentUser(
                olares_username=olares_username,
                user_id=user_id,
                org_id=org["id"],
                display_name=display_name,
            )


async def get_current_user(
    x_bfl_user: str | None = Header(None, alias="X-Bfl-User"),
) -> CurrentUser:
    if not x_bfl_user:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Bfl-User header. Reach this API via Olares Envoy.",
        )
    return await _ensure_user_and_org(x_bfl_user)


# Re-export for convenience in router dependencies
__all__ = ["CurrentUser", "get_current_user"]
