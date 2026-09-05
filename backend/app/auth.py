"""Olares-Header-based identity + auto-provisioning of dev users."""

from uuid import UUID

from fastapi import Header, HTTPException, Request
from pydantic import BaseModel

from app import audit
from app.config import settings
from app.db import acquire


class CurrentUser(BaseModel):
    """User-Identität aus Olares-Authelia-Header (X-Bfl-User) + DB-Mapping."""

    olares_username: str
    user_id: UUID
    org_id: UUID
    display_name: str | None = None


async def _ensure_user_and_org(olares_username: str) -> CurrentUser:
    """Identität auflösen — und nur in der Entwicklung anlegen.

    Bis hierher legte ein unbekannter Name stillschweigend **einen neuen
    Nutzer samt eigener Organisation** an. Als Bequemlichkeit für die
    lokale Entwicklung gedacht, in Betrieb aber eine Selbstbedienung: wer
    das Backend erreicht und einen ausgedachten Namen schickt, bekam eine
    frische Organisation und war darin Inhaber.

    `INSILO_AUTO_PROVISION` schaltet das frei. Vorgabe ist aus; das
    Deployment setzt es nicht. Ohne die Freigabe endet ein unbekannter
    Name mit 401 — Nutzer und Organisation legt dann das Onboarding an.
    """
    async with acquire() as conn:
        if not settings.auto_provision:
            gefunden = await conn.fetchrow(
                """
                select u.id, u.display_name, r.org_id
                from public.users u
                join public.user_org_roles r on r.user_id = u.id
                join public.orgs o on o.id = r.org_id and o.deleted_at is null
                where u.olares_username = $1
                limit 1
                """,
                olares_username,
            )
            if gefunden is None:
                raise HTTPException(
                    status_code=401,
                    detail="Unknown identity. Ask an administrator to add this user.",
                )
            await conn.execute(
                "update public.users set last_seen_at = now() where id = $1",
                gefunden["id"],
            )
            return CurrentUser(
                olares_username=olares_username,
                user_id=gefunden["id"],
                org_id=gefunden["org_id"],
                display_name=gefunden["display_name"],
            )

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
    request: Request,
    x_bfl_user: str | None = Header(None, alias="X-Bfl-User"),
) -> CurrentUser:
    if not x_bfl_user:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Bfl-User header. Reach this API via Olares Envoy.",
        )
    user = await _ensure_user_and_org(x_bfl_user)
    # Den aufgelösten Urheber fürs Protokoll hinterlegen. Die Middleware
    # könnte ihn nicht selbst holen, ohne diesen Aufruf zu wiederholen —
    # und der legt unbekannte Benutzer beim Auflösen an.
    audit.merke_akteur(
        request.scope,
        user_id=user.user_id,
        org_id=user.org_id,
        olares_user=user.olares_username,
    )
    return user


# Re-export for convenience in router dependencies
__all__ = ["CurrentUser", "get_current_user"]
