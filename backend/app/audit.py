"""Protokoll — wer hat wann was geändert oder ausgeleitet.

`public.audit_log` liegt seit Migration 0001 bereit, mit vier Indizes und
einer RLS-Regel. Geschrieben hat bis hierher niemand hinein. CLAUDE.md
verspricht derweil „Audit-Trail. Jede Datenänderung wird geloggt" — und
das Zielsegment sind Kanzleien und Steuerberatungen, deren
Datenschutzbeauftragte genau danach fragen.

**Eine Stelle, nicht zwölf.** Geschrieben wird aus einer Middleware
(`app.main.protokoll_middleware`), nicht aus den Endpunkten. Damit ist
auch protokolliert, was es heute noch gar nicht gibt: ein neuer
schreibender Endpunkt landet im Protokoll, ohne dass jemand daran denken
muss. Dasselbe Muster wie beim Konfigurations-Abzug.

**Der Urheber kostet keine zusätzliche Abfrage.** Die Middleware kann den
Benutzer nicht selbst auflösen — `get_current_user` legt ihn beim
Auflösen an, ein zweiter Aufruf wäre eine zweite Schreiboperation. Statt
dessen hinterlegen die beiden Auth-Wege (`app.auth.get_current_user` für
die Oberfläche, `app.auth_api.get_api_caller` für die externe
Schnittstelle) den bereits aufgelösten Urheber im ASGI-`scope`. Der ist
zwischen Middleware und Endpunkt dasselbe Wörterbuch — anders als
ContextVars, die aus einer `BaseHTTPMiddleware` heraus nicht nach oben
durchschlagen, weil Starlette den nachgelagerten Aufruf in eine eigene
Task legt.

**Was nicht hineingeschrieben wird:** der Wortlaut einer Suchanfrage.
Dass jemand das Archiv befragt hat, gehört ins Protokoll; *wonach* er
gefragt hat, wäre Gesprächsinhalt in einer Tabelle, die Inhaberinnen und
Verwaltende der Organisation vollständig lesen dürfen. Der Vorgang wird
festgehalten, der Inhalt nicht.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg

log = logging.getLogger(__name__)

# Schlüssel im ASGI-scope. Kein `request.state`: dessen Anbindung an den
# scope hat sich zwischen Starlette-Fassungen verschoben, der scope selbst
# ist seit jeher dasselbe Wörterbuch.
_SCOPE_SCHLUESSEL = "insilo_protokoll"

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


@dataclass
class Vorgang:
    """Was ein Aufruf im Protokoll bedeutet."""

    aktion: str
    art: str | None = None
    kennung: UUID | None = None
    # Von Endpunkten nachgereicht (`ergaenze`), etwa die Kennung einer neu
    # angelegten Besprechung, die erst in der Antwort entsteht.
    zusatz: dict[str, Any] = field(default_factory=dict)
    aenderungen: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Pfad → Vorgang
#
# Reihenfolge zählt: die erste passende Zeile gewinnt, längere Pfade stehen
# deshalb vor ihren Präfixen (`/templates/{id}/prompt` vor `/templates/{id}`).
# ---------------------------------------------------------------------------

_REGELN: list[tuple[frozenset[str], re.Pattern[str], str, str | None]] = [
    # ── Besprechungen ──────────────────────────────────────────────────
    (frozenset({"POST"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/dispatch$"),
     "meeting.dispatch", "meeting"),
    (frozenset({"POST"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/restore$"),
     "meeting.restore", "meeting"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/permanent$"),
     "meeting.purge", "meeting"),
    (frozenset({"POST"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/retry-summary$"),
     "meeting.resummarize", "meeting"),
    (frozenset({"POST"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/re-diarize$"),
     "meeting.rediarize", "meeting"),
    (frozenset({"PUT"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/transcript/speakers$"),
     "transcript.rename_speakers", "meeting"),
    (frozenset({"POST"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/clusters/\d+/assign$"),
     "meeting.assign_speaker", "meeting"),
    (frozenset({"POST"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/tags$"),
     "meeting.tag", "meeting"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})/tags/{_UUID}$"),
     "meeting.untag", "meeting"),
    (frozenset({"PATCH"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})$"),
     "meeting.update", "meeting"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/meetings/(?P<id>{_UUID})$"),
     "meeting.delete", "meeting"),
    (frozenset({"POST"}), re.compile(r"^/api/v1/recordings$"),
     "meeting.create", "meeting"),

    # ── Ausleitung: Inhalte gehen an ein Sprachmodell ──────────────────
    (frozenset({"POST"}), re.compile(r"^/api/v1/ask$"), "archive.ask", None),
    (frozenset({"POST"}), re.compile(r"^/api/v1/search$"), "archive.search", None),

    # ── Ausleitung: externe Schnittstelle (Zugriffsschlüssel) ──────────
    (frozenset({"GET"}), re.compile(rf"^/api/external/v1/meetings/(?P<id>{_UUID})/markdown$"),
     "external.export_markdown", "meeting"),
    (frozenset({"GET"}), re.compile(rf"^/api/external/v1/meetings/(?P<id>{_UUID})$"),
     "external.read_meeting", "meeting"),
    (frozenset({"GET"}), re.compile(r"^/api/external/v1/meetings$"),
     "external.list_meetings", None),

    # ── Einrichtung ────────────────────────────────────────────────────
    (frozenset({"POST"}), re.compile(r"^/api/v1/webhooks/(?P<id>" + _UUID + r")/test$"),
     "webhook.test", "webhook"),
    (frozenset({"POST"}), re.compile(r"^/api/v1/webhooks$"), "webhook.create", "webhook"),
    (frozenset({"PUT"}), re.compile(rf"^/api/v1/webhooks/(?P<id>{_UUID})$"),
     "webhook.update", "webhook"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/webhooks/(?P<id>{_UUID})$"),
     "webhook.delete", "webhook"),

    (frozenset({"POST"}), re.compile(r"^/api/v1/api-keys$"), "api_key.create", "api_key"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/api-keys/(?P<id>{_UUID})$"),
     "api_key.revoke", "api_key"),

    (frozenset({"POST"}), re.compile(r"^/api/v1/settings/test$"), "settings.test", None),
    (frozenset({"PUT"}), re.compile(r"^/api/v1/settings$"), "settings.update", None),
    (frozenset({"PUT"}), re.compile(r"^/api/v1/locale$"), "settings.locale", None),

    (frozenset({"PUT"}), re.compile(rf"^/api/v1/templates/(?P<id>{_UUID})/prompt$"),
     "template.prompt_update", "template"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/templates/(?P<id>{_UUID})/prompt$"),
     "template.prompt_reset", "template"),
    (frozenset({"POST"}), re.compile(r"^/api/v1/templates$"), "template.create", "template"),
    (frozenset({"PUT"}), re.compile(rf"^/api/v1/templates/(?P<id>{_UUID})$"),
     "template.update", "template"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/templates/(?P<id>{_UUID})$"),
     "template.delete", "template"),

    (frozenset({"POST"}), re.compile(r"^/api/v1/tags$"), "tag.create", "tag"),
    (frozenset({"PUT"}), re.compile(rf"^/api/v1/tags/(?P<id>{_UUID})$"), "tag.update", "tag"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/tags/(?P<id>{_UUID})$"), "tag.delete", "tag"),

    (frozenset({"POST"}), re.compile(rf"^/api/v1/speakers/(?P<id>{_UUID})/enroll$"),
     "speaker.enroll", "speaker"),
    (frozenset({"POST"}), re.compile(r"^/api/v1/speakers$"), "speaker.create", "speaker"),
    (frozenset({"PUT"}), re.compile(rf"^/api/v1/speakers/(?P<id>{_UUID})$"),
     "speaker.update", "speaker"),
    (frozenset({"DELETE"}), re.compile(rf"^/api/v1/speakers/(?P<id>{_UUID})$"),
     "speaker.delete", "speaker"),
]

# Vorgänge, die an keinem Pfad hängen und deshalb nicht aus `_REGELN`
# fallen können. Die Anmeldung ist kein Endpunkt — sie geschieht in
# `auth.py`, bevor irgendein Router an die Reihe kommt.
ERSTEINRICHTUNG = "org.ersteinrichtung"

OHNE_PFAD: tuple[str, ...] = (ERSTEINRICHTUNG,)

# Für die Oberfläche: alle Aktionen, die es geben kann. Der Filter im
# Protokoll baut daraus seine Auswahl, statt zu raten, was vorkommt.
AKTIONEN: tuple[str, ...] = tuple(
    dict.fromkeys((*(regel[2] for regel in _REGELN), *OHNE_PFAD))
)

# Vorgänge, bei denen Daten die Box verlassen können. Die Oberfläche hebt
# sie hervor — für einen Datenschutzbeauftragten ist das die
# interessanteste Teilmenge.
AUSLEITUNG: frozenset[str] = frozenset({
    "meeting.dispatch",
    "external.export_markdown",
    "external.read_meeting",
    "external.list_meetings",
    "archive.ask",
    "archive.search",
    "webhook.test",
    "settings.test",
})


def deuten(methode: str, pfad: str) -> Vorgang | None:
    """Was bedeutet dieser Aufruf? `None` heißt: nichts Protokollwürdiges.

    Lesende Aufrufe der eigenen Oberfläche stehen bewusst nicht in der
    Tabelle. Ein Protokoll, das jeden Seitenaufruf mitschreibt, ist nach
    einer Woche nicht mehr lesbar — und die Frage, die es beantworten
    soll, lautet „wer hat etwas verändert oder herausgegeben".
    """
    for methoden, muster, aktion, art in _REGELN:
        if methode not in methoden:
            continue
        treffer = muster.match(pfad)
        if treffer is None:
            continue
        kennung: UUID | None = None
        if "id" in treffer.groupdict():
            try:
                kennung = UUID(treffer.group("id"))
            except (ValueError, TypeError):  # pragma: no cover — Muster erzwingt die Form
                kennung = None
        return Vorgang(aktion=aktion, art=art, kennung=kennung)
    return None


# ---------------------------------------------------------------------------
# Urheber und Nachträge — hinterlegt im ASGI-scope
# ---------------------------------------------------------------------------


def _ablage(scope: dict[str, Any]) -> dict[str, Any]:
    ablage = scope.get(_SCOPE_SCHLUESSEL)
    if ablage is None:
        ablage = {}
        scope[_SCOPE_SCHLUESSEL] = ablage
    return ablage


def merke_akteur(
    scope: dict[str, Any],
    *,
    user_id: UUID | None = None,
    org_id: UUID | None = None,
    olares_user: str | None = None,
    api_key_id: UUID | None = None,
) -> None:
    """Vom Auth-Weg gerufen, sobald der Urheber feststeht.

    Erspart der Middleware eine eigene Auflösung — und damit im Fall der
    Oberfläche eine zweite Schreiboperation, denn `get_current_user` legt
    unbekannte Benutzer beim Auflösen an.
    """
    _ablage(scope).update(
        {
            "user_id": user_id,
            "org_id": org_id,
            "olares_user": olares_user,
            "api_key_id": api_key_id,
        }
    )


def ergaenze(
    scope: dict[str, Any],
    *,
    kennung: UUID | None = None,
    zusatz: dict[str, Any] | None = None,
    aenderungen: dict[str, Any] | None = None,
) -> None:
    """Freiwilliger Nachtrag aus einem Endpunkt.

    Für das, was die Middleware nicht am Pfad ablesen kann — die Kennung
    einer eben angelegten Besprechung etwa entsteht erst in der Antwort.
    Wer es vergisst, verliert einen Nachtrag, nie den Eintrag.
    """
    ablage = _ablage(scope)
    if kennung is not None:
        ablage["kennung"] = kennung
    if zusatz:
        ablage.setdefault("zusatz", {}).update(zusatz)
    if aenderungen:
        ablage["aenderungen"] = aenderungen


async def akteur_nachschlagen(
    conn: asyncpg.Connection, scope: dict[str, Any], headers: dict[str, str]
) -> None:
    """Urheber notfalls selbst auflösen, wenn der Auth-Weg nicht lief.

    Scheitert eine Anfrage schon an der Eingabeprüfung, ruft FastAPI den
    Endpunkt nie auf — und damit auch `get_current_user` nicht, das den
    Urheber sonst hinterlegt. Der Eintrag hätte dann keine Organisation,
    und weil die Ansicht nach Organisation filtert, wäre er **für
    niemanden sichtbar**: ein Vorgang, der protokolliert ist und den
    trotzdem keiner findet. Genau das darf ein Protokoll nicht.

    Deshalb hier ein reines `select` auf den Kopfwert — kein `insert`.
    Anlegen darf nur der Auth-Weg; ein unbekannter Name bekommt seinen
    Eintrag ohne Kennung, aber mit Namen.
    """
    ablage = _ablage(scope)
    if ablage.get("user_id") or ablage.get("api_key_id"):
        return
    kopf = (headers.get("x-bfl-user") or "").strip()
    if not kopf:
        # Ohne Kopfzeile gibt es niemanden zu benennen. In Betrieb kann
        # das nicht vorkommen: der Envoy-Sidecar setzt sie, bevor eine
        # Anfrage uns überhaupt erreicht.
        return

    zeile = await conn.fetchrow(
        """
        select u.id as user_id, r.org_id
        from public.users u
        left join public.user_org_roles r on r.user_id = u.id
        where u.olares_username = $1
        limit 1
        """,
        kopf,
    )
    ablage["olares_user"] = kopf
    if zeile is not None:
        ablage["user_id"] = zeile["user_id"]
        ablage["org_id"] = zeile["org_id"]


def _herkunft(headers: dict[str, str], client: str | None) -> str | None:
    """Absender-Adresse — hinter Envoy steht die echte im Forwarded-Kopf.

    Ungültige Werte werden verworfen statt weitergereicht: die Spalte ist
    `inet`, ein frei gewählter Kopfwert würde den Eintrag sonst
    verhindern — ausgerechnet den, der jemanden interessiert.
    """
    weitergabe = headers.get("x-forwarded-for")
    kandidaten = []
    if weitergabe:
        kandidaten.append(weitergabe.split(",")[0].strip())
    if client:
        kandidaten.append(client)
    for kandidat in kandidaten:
        try:
            return str(ipaddress.ip_address(kandidat))
        except ValueError:
            continue
    return None


async def aufzeichnen(
    conn: asyncpg.Connection,
    *,
    vorgang: Vorgang,
    scope: dict[str, Any],
    headers: dict[str, str],
    client: str | None,
    status: int,
) -> None:
    """Einen Eintrag schreiben. Wirft — die Middleware fängt."""
    await akteur_nachschlagen(conn, scope, headers)
    ablage = _ablage(scope)
    kennung = ablage.get("kennung") or vorgang.kennung
    zusatz: dict[str, Any] = {
        "methode": scope.get("method"),
        "pfad": scope.get("path"),
        "status": status,
        **(ablage.get("zusatz") or {}),
    }
    if vorgang.aktion in AUSLEITUNG:
        zusatz["ausleitung"] = True

    aenderungen = ablage.get("aenderungen")

    await conn.execute(
        """
        insert into public.audit_log
            (user_id, olares_user, org_id, api_key_id, action, resource_type,
             resource_id, ip_address, user_agent, changes, success, metadata)
        values ($1, $2, $3, $4, $5, $6, $7, $8::inet, $9, $10::jsonb, $11, $12::jsonb)
        """,
        ablage.get("user_id"),
        ablage.get("olares_user"),
        ablage.get("org_id"),
        ablage.get("api_key_id"),
        vorgang.aktion,
        vorgang.art,
        kennung,
        _herkunft(headers, client),
        (headers.get("user-agent") or "")[:500] or None,
        json.dumps(aenderungen) if aenderungen else None,
        status < 400,
        json.dumps(zusatz),
    )
