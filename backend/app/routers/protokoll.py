"""Lesezugriff auf das Protokoll (`public.audit_log`).

Geschrieben wird aus der Middleware in `app.main`, hier wird nur gelesen.

**Wer was sehen darf**, steht seit Migration 0002 als RLS-Regel in der
Datenbank: eigene Einträge immer, alle Einträge der Organisation nur als
Inhaberin oder Verwaltende. Seit Migration 0017 greift die Regel auch
wirklich — `acquire_as` setzt den Nutzerkontext, den sie liest, und
`force row level security` gilt auch für die Eigentümerin der Tabellen.

Die Bedingung steht **zusätzlich** in der Abfrage. Nicht aus Misstrauen
gegen die Regel, sondern damit die Ansicht dasselbe zeigt, wenn jemand
sie einmal ohne Kontext aufruft. Wer eine davon ändert, ändert beide.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app import audit
from app.auth import CurrentUser, get_current_user
from app.db import acquire_as

router = APIRouter(prefix="/api/v1", tags=["protokoll"])

# Obergrenze pro Abruf. Die Oberfläche blättert; ein offenes Limit würde
# bei einer vielbenutzten Box das Backend beschäftigen, ohne dass jemand
# so viele Zeilen liest.
MAX_ANZAHL = 200


class Eintrag(BaseModel):
    id: str
    zeitpunkt: str
    aktion: str
    urheber: str | None
    urheber_art: str  # "user" | "api_key" | "unbekannt"
    art: str | None
    kennung: str | None
    bezeichnung: str | None  # Titel der Besprechung, falls noch vorhanden
    erfolg: bool
    ausleitung: bool
    herkunft: str | None
    zusatz: dict[str, Any]


class Seite(BaseModel):
    eintraege: list[Eintrag]
    hat_mehr: bool
    darf_alles_sehen: bool


class Auswahl(BaseModel):
    """Was die Oberfläche zum Filtern anbieten kann."""

    aktionen: list[str]
    ausleitung: list[str]


@router.get("/protokoll/auswahl", response_model=Auswahl)
async def filter_auswahl(
    user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — nur Zugangsschutz
) -> Auswahl:
    """Die möglichen Aktionen — damit die Oberfläche nicht raten muss.

    Aus derselben Tabelle wie die Middleware, nicht aus einer zweiten
    Liste: eine neue Regel in `audit._REGELN` taucht hier automatisch auf.
    """
    return Auswahl(aktionen=list(audit.AKTIONEN), ausleitung=sorted(audit.AUSLEITUNG))


async def _darf_alles_sehen(conn, user: CurrentUser) -> bool:
    rolle = await conn.fetchval(
        """
        select role from public.user_org_roles
        where user_id = $1 and org_id = $2
        """,
        user.user_id,
        user.org_id,
    )
    return rolle in ("owner", "admin")


@router.get("/protokoll", response_model=Seite)
async def protokoll_lesen(
    aktion: list[str] = Query(default_factory=list),
    nur_ausleitung: bool = Query(default=False),
    von: datetime | None = Query(default=None),
    bis: datetime | None = Query(default=None),
    anzahl: int = Query(default=50, ge=1, le=MAX_ANZAHL),
    ab: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(get_current_user),
) -> Seite:
    """Protokolleinträge, neueste zuerst.

    `nur_ausleitung` schränkt auf die Vorgänge ein, bei denen Inhalte die
    Box verlassen können — die Teilmenge, nach der ein
    Datenschutzbeauftragter fragt.
    """
    ausleitung = sorted(audit.AUSLEITUNG)
    gefragte_aktionen = [a for a in aktion if a in audit.AKTIONEN]

    async with acquire_as(user.user_id) as conn:
        alles = await _darf_alles_sehen(conn, user)

        rows = await conn.fetch(
            """
            select l.id, l.timestamp, l.action, l.resource_type, l.resource_id,
                   l.olares_user, l.api_key_id, l.success, l.ip_address, l.metadata,
                   k.name as key_name,
                   m.title as meeting_title
            from public.audit_log l
            left join public.api_keys k on k.id = l.api_key_id
            left join public.meetings m
                   on l.resource_type = 'meeting' and m.id = l.resource_id
            where l.org_id = $1
              and ($2::boolean or l.user_id = $3)
              and (cardinality($4::text[]) = 0 or l.action = any($4::text[]))
              and (not $5::boolean or l.action = any($6::text[]))
              and ($7::timestamptz is null or l.timestamp >= $7)
              and ($8::timestamptz is null or l.timestamp <= $8)
            order by l.timestamp desc
            limit $9 offset $10
            """,
            user.org_id,
            alles,
            user.user_id,
            gefragte_aktionen,
            nur_ausleitung,
            ausleitung,
            von,
            bis,
            # Eine Zeile mehr holen, statt zu zählen: beantwortet „gibt es
            # weitere" ohne count(*) über die ganze Tabelle.
            anzahl + 1,
            ab,
        )

    hat_mehr = len(rows) > anzahl
    return Seite(
        eintraege=[_zu_eintrag(r) for r in rows[:anzahl]],
        hat_mehr=hat_mehr,
        darf_alles_sehen=alles,
    )


def _zu_eintrag(row) -> Eintrag:
    if row["api_key_id"] is not None:
        urheber = row["key_name"] or "Zugriffsschlüssel"
        urheber_art = "api_key"
    elif row["olares_user"]:
        urheber = row["olares_user"]
        urheber_art = "user"
    else:
        urheber = None
        urheber_art = "unbekannt"

    zusatz = row["metadata"]
    if isinstance(zusatz, str):
        # asyncpg gibt jsonb als Zeichenkette zurück, wenn kein Codec
        # gesetzt ist — dieselbe Falle wie beim Konfigurations-Abzug
        # (HANDOFF, v0.1.81).
        try:
            zusatz = json.loads(zusatz)
        except ValueError:
            zusatz = {}
    if not isinstance(zusatz, dict):
        zusatz = {}

    return Eintrag(
        id=str(row["id"]),
        zeitpunkt=row["timestamp"].isoformat(),
        aktion=row["action"],
        urheber=urheber,
        urheber_art=urheber_art,
        art=row["resource_type"],
        kennung=str(row["resource_id"]) if row["resource_id"] else None,
        bezeichnung=row["meeting_title"],
        erfolg=row["success"],
        ausleitung=row["action"] in audit.AUSLEITUNG,
        herkunft=str(row["ip_address"]) if row["ip_address"] else None,
        zusatz=zusatz,
    )
