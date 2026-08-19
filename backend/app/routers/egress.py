"""Datenschutz-Nachweis: was verlässt diese Box?

Liefert ausschließlich Belegbares — die effektive LLM-Konfiguration, die
aktiven Webhooks und die tatsächlich zugestellten Bytes aus dem
Audit-Log. Nichts wird geschätzt oder hochgerechnet.

Das AImighty-Designsystem verlangt für den Nachweis in der Navigation
gemessene Werte „oder gar nicht". Wo keine Zustellung stattgefunden hat,
liefert dieser Endpunkt darum `gesendete_bytes: null` statt einer Null —
die Oberfläche unterscheidet „nichts gesendet" von „nicht gemessen".
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.db import acquire
from app.egress import ist_boxintern, ist_eigene_zone
from app.llm_config import load_llm_config
from app.stt_config import load_stt_config

router = APIRouter(prefix="/api/v1", tags=["egress"])


class ZielRead(BaseModel):
    art: str  # "stt" | "llm" | "webhook"
    host: str
    beschreibung: str


class EgressRead(BaseModel):
    # Kernaussage — trägt die Anzeige in der Navigation.
    alles_bleibt: bool

    # `llm_extern` meint: bei einem fremden Anbieter. Die eigene Box unter
    # ihrer öffentlichen Adresse zählt nicht dazu — der Aufruf geht zwar
    # hinaus und wieder herein, bleibt aber auf derselben Maschine.
    llm_extern: bool
    llm_eigene_box: bool
    # Kein Endpunkt eingetragen. Weder Warnung noch Entwarnung — es fehlt
    # etwas, und die Oberfläche sagt das statt zu beruhigen.
    llm_fehlt: bool
    llm_host: str | None

    # Spracherkennung. Ohne eingetragene Adresse transkribiert der
    # mitgelieferte Dienst und das Audio bleibt, wo es ist — das ist der
    # Normalfall, deshalb heißt das Feld nicht „fehlt".
    stt_lokal: bool
    stt_extern: bool
    stt_eigene_box: bool
    stt_host: str | None

    webhooks_aktiv: int
    ziele: list[ZielRead]

    # null = es gab nie eine Zustellung. 0 wäre eine Messung, die es so
    # nicht gibt: jeder Payload hat einen Rumpf.
    gesendete_bytes: int | None
    zustellungen: int
    letzter_versand: str | None


def _host(url: str) -> str:
    return urlsplit(url.strip()).hostname or url.strip()


@router.get("/egress", response_model=EgressRead)
async def read_egress(user: CurrentUser = Depends(get_current_user)) -> EgressRead:
    async with acquire() as conn:
        llm = await load_llm_config(conn, user.org_id)
        # Drei Lagen statt zwei: clusterintern, eigene Box über die
        # öffentliche Adresse, fremder Anbieter. Nur das Letzte ist ein
        # Grund zur Warnung.
        llm_fehlt = not llm.eingerichtet
        eigene_box = not llm_fehlt and ist_eigene_zone(llm.base_url)
        llm_extern = (
            not llm_fehlt and not ist_boxintern(llm.base_url) and not eigene_box
        )

        # Audio ist das empfindlichste, was Insilo hat. Bis v0.1.76 konnte
        # es die Box gar nicht verlassen; seit dem konfigurierbaren
        # STT-Endpunkt kann es das, und dann gehört es benannt.
        stt = await load_stt_config(conn, user.org_id)
        stt_lokal = not stt.eingerichtet
        stt_eigene_box = not stt_lokal and ist_eigene_zone(stt.base_url)
        stt_extern = (
            not stt_lokal
            and not ist_boxintern(stt.base_url)
            and not stt_eigene_box
        )

        webhooks = await conn.fetch(
            """
            select url, description
            from public.org_webhooks
            where org_id = $1 and is_active = true
            order by created_at
            """,
            user.org_id,
        )

        # Nur Zustellungen an Webhooks dieser Org, und nur solche mit
        # gemessener Größe (vor Migration 0014 ist request_bytes NULL).
        summe = await conn.fetchrow(
            """
            select
                sum(d.request_bytes)            as bytes,
                count(d.request_bytes)          as gemessen,
                max(d.created_at)               as zuletzt
            from public.webhook_deliveries d
            join public.org_webhooks w on w.id = d.webhook_id
            where w.org_id = $1
            """,
            user.org_id,
        )

    ziele: list[ZielRead] = []
    if stt_extern:
        ziele.append(
            ZielRead(
                art="stt",
                host=_host(stt.base_url),
                beschreibung=stt.model or "",
            )
        )
    if llm_extern:
        ziele.append(
            ZielRead(
                art="llm",
                host=_host(llm.base_url),
                beschreibung=llm.model or "",
            )
        )
    for w in webhooks:
        ziele.append(
            ZielRead(
                art="webhook",
                host=_host(w["url"]),
                beschreibung=w["description"] or "",
            )
        )

    gemessen = int(summe["gemessen"] or 0) if summe else 0
    zuletzt = summe["zuletzt"] if summe else None

    return EgressRead(
        # „Alles bleibt" nur, wenn wirklich nichts hinausgeht — Audio
        # eingeschlossen. Ein externer STT-Endpunkt schließt die Aussage
        # aus, auch wenn LLM und Webhooks sauber sind.
        alles_bleibt=not llm_extern and not stt_extern and len(webhooks) == 0,
        llm_extern=llm_extern,
        llm_eigene_box=eigene_box,
        llm_fehlt=llm_fehlt,
        # Auch bei der eigenen Box den Host zeigen — der Nutzer soll sehen,
        # worüber gesprochen wird, nicht nur dass alles gut ist.
        llm_host=_host(llm.base_url) if (llm_extern or eigene_box) else None,
        stt_lokal=stt_lokal,
        stt_extern=stt_extern,
        stt_eigene_box=stt_eigene_box,
        stt_host=_host(stt.base_url) if (stt_extern or stt_eigene_box) else None,
        webhooks_aktiv=len(webhooks),
        ziele=ziele,
        gesendete_bytes=int(summe["bytes"]) if gemessen and summe["bytes"] else None,
        zustellungen=gemessen,
        letzter_versand=zuletzt.isoformat() if zuletzt else None,
    )
