"""Olares-Header-based identity + auto-provisioning of dev users."""

import json
import logging
from uuid import UUID

import asyncpg
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel

from app import audit, konfiguration
from app.config import settings
from app.db import acquire, acquire_als_dienst

log = logging.getLogger(__name__)

# Beliebige, aber feste Zahl: zwei gleichzeitige erste Aufrufe müssen sich
# an derselben Sperre treffen. Nur in `_erstzugang` verwendet.
_SPERRE_ERSTZUGANG = 815_102_026


class CurrentUser(BaseModel):
    """User-Identität aus Olares-Authelia-Header (X-Bfl-User) + DB-Mapping."""

    olares_username: str
    user_id: UUID
    org_id: UUID
    display_name: str | None = None


async def _erstzugang(
    conn: asyncpg.Connection, olares_username: str
) -> CurrentUser | None:
    """Die erste Identität auf einer leeren Box wird ihre Inhaberin.

    **Warum es das gibt.** Seit v0.1.85 ist die Selbstbedienung aus
    (`INSILO_AUTO_PROVISION`, Vorgabe aus, das Chart setzt sie nie), und
    `konfiguration.wiederherstellen` greift nur, wenn
    `/app/data/konfiguration.json` bereits existiert — bei einer echten
    Neuinstallation tut sie das nicht. Damit legte **niemand** den ersten
    Nutzer an: der erste Aufruf einer frisch installierten Box endete mit
    401, und die Box war unbenutzbar, bis jemand mit `psql` daneben ging.

    **Der Unterschied zur alten Selbstbedienung ist die Bedingung.** Dort
    bekam *jeder* unbekannte Name eine eigene Organisation, jederzeit und
    beliebig oft. Hier geht das genau einmal, nämlich solange **keine**
    Organisation existiert. Ab der ersten bleibt es beim 401 — auch für
    den zweiten Namen, der eine Sekunde später anklopft. Die Bedingung
    ist dieselbe, die `konfiguration.wiederherstellen` „leer" nennt:
    eine Regel, eine Stelle.

    **Wer hier ankommt, ist bereits angemeldet.** Das Backend nimmt
    Aufrufe nur mit dem gemeinsamen Geheimnis an (Torwächter in
    `main.py`), und `X-Bfl-User` setzt die Middleware des Frontends
    serverseitig aus `Remote-User` — dem, was der Auth-Dienst der Box
    nach oben reicht. Das Fenster steht also nicht dem Netz offen,
    sondern den bei Olares angemeldeten Personen dieser Box.
    """
    async with conn.transaction():
        # Erst sperren, dann nachsehen: zwei gleichzeitige erste Aufrufe
        # würden sonst beide „leer" lesen und zwei Organisationen
        # anlegen. Die Sperre fällt am Ende der Transaktion, auch bei
        # einem Fehler.
        await conn.execute("select pg_advisory_xact_lock($1)", _SPERRE_ERSTZUGANG)

        if await conn.fetchval(
            "select count(*) from public.orgs where deleted_at is null"
        ):
            return None

        org_id = await conn.fetchval(
            """
            insert into public.orgs (name, slug)
            values ($1, $2)
            returning id
            """,
            f"Organisation {olares_username}",
            f"org-{olares_username}",
        )
        row = await conn.fetchrow(
            """
            insert into public.users (olares_username, display_name)
            values ($1, $1)
            on conflict (olares_username) do update set last_seen_at = now()
            returning id, display_name
            """,
            olares_username,
        )
        await conn.execute(
            """
            insert into public.user_org_roles (user_id, org_id, role)
            values ($1, $2, 'owner')
            """,
            row["id"],
            org_id,
        )
        # Ins Protokoll, nicht nur ins Anwendungslog: „wer wurde wann
        # Inhaber dieser Box" ist genau die Frage, für die es das
        # Protokoll gibt. Die Middleware kann diesen Vorgang nicht
        # erfassen — er hängt an keinem Pfad.
        await conn.execute(
            """
            insert into public.audit_log
                (user_id, olares_user, org_id, action, resource_type,
                 resource_id, metadata)
            values ($1, $2, $3, $4, 'org', $3, $5::jsonb)
            """,
            row["id"],
            olares_username,
            org_id,
            audit.ERSTEINRICHTUNG,
            json.dumps({"name": f"Organisation {olares_username}"}),
        )

    log.warning(
        "Erstzugang: die Box war leer, %r ist jetzt Inhaber von %s",
        olares_username,
        org_id,
    )

    # Den Abzug sofort schreiben. Er trägt die Kennung der Organisation,
    # und an der hängt der Pfad der Tonaufnahmen (`audio/<org-id>/`) —
    # ohne ihn bekäme die Box nach einer Neuinstallation eine neue
    # Kennung und die vorhandenen Aufnahmen hätten niemanden mehr.
    try:
        async with acquire_als_dienst() as dienst:
            await konfiguration.sichern_leise(dienst)
    except Exception as exc:  # noqa: BLE001
        # Wie überall beim Abzug: eine Bequemlichkeit, keine Bedingung.
        log.warning("Konfigurations-Abzug nach dem Erstzugang übersprungen: %s", exc)

    return CurrentUser(
        olares_username=olares_username,
        user_id=row["id"],
        org_id=org_id,
        display_name=row["display_name"],
    )


async def _ensure_user_and_org(olares_username: str) -> CurrentUser:
    """Identität auflösen — und nur in der Entwicklung anlegen.

    Bis hierher legte ein unbekannter Name stillschweigend **einen neuen
    Nutzer samt eigener Organisation** an. Als Bequemlichkeit für die
    lokale Entwicklung gedacht, in Betrieb aber eine Selbstbedienung: wer
    das Backend erreicht und einen ausgedachten Namen schickt, bekam eine
    frische Organisation und war darin Inhaber.

    `INSILO_AUTO_PROVISION` schaltet das frei. Vorgabe ist aus; das
    Deployment setzt es nicht. Ohne die Freigabe endet ein unbekannter
    Name mit 401 — mit der einen Ausnahme in `_erstzugang`: solange es
    überhaupt keine Organisation gibt, wird die erste Identität ihre
    Inhaberin. Sonst käme auf eine frisch installierte Box niemand.
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
                erster = await _erstzugang(conn, olares_username)
                if erster is not None:
                    return erster
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
