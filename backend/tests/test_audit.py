"""Prüft das Protokoll — vor allem, dass es nichts übersieht.

Der Anlass steht in app/audit.py: `public.audit_log` lag seit Migration
0001 bereit und wurde nie beschrieben, während CLAUDE.md „jede
Datenänderung wird geloggt" versprach.

Der wichtigste Test hier ist `test_jeder_schreibende_endpunkt_wird_gedeutet`.
Er hält die Zusage „eine Stelle, nicht zwölf" fest: wer künftig einen
schreibenden Endpunkt hinzufügt, ohne eine Regel in `audit._REGELN`,
bekommt einen roten Test statt eines stillen Lochs im Protokoll.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID, uuid4

from app import audit

BEISPIEL = UUID("11111111-2222-3333-4444-555555555555")


# ---------------------------------------------------------------------------
# Deutung
# ---------------------------------------------------------------------------


def test_lesende_oberflaechen_aufrufe_stehen_nicht_im_protokoll() -> None:
    """Sonst ist das Protokoll nach einer Woche nicht mehr lesbar.

    Die Frage, die es beantworten soll, lautet „wer hat etwas verändert
    oder herausgegeben" — nicht „wer hat eine Liste geöffnet".
    """
    assert audit.deuten("GET", "/api/v1/meetings") is None
    assert audit.deuten("GET", f"/api/v1/meetings/{BEISPIEL}") is None
    assert audit.deuten("GET", "/api/v1/templates") is None
    assert audit.deuten("GET", "/health") is None


def test_loeschen_zurueckholen_und_endgueltig_sind_verschiedene_vorgaenge() -> None:
    """Drei Wege, die im Protokoll auseinandergehalten werden müssen.

    „Gelöscht" und „endgültig entfernt" ist für eine Rückfrage ein
    Unterschied ums Ganze.
    """
    weg = audit.deuten("DELETE", f"/api/v1/meetings/{BEISPIEL}")
    zurueck = audit.deuten("POST", f"/api/v1/meetings/{BEISPIEL}/restore")
    endgueltig = audit.deuten("DELETE", f"/api/v1/meetings/{BEISPIEL}/permanent")

    assert weg is not None and weg.aktion == "meeting.delete"
    assert zurueck is not None and zurueck.aktion == "meeting.restore"
    assert endgueltig is not None and endgueltig.aktion == "meeting.purge"
    # Die Kennung wird aus dem Pfad gelesen, sonst stünde im Protokoll
    # „jemand hat etwas gelöscht".
    assert {weg.kennung, zurueck.kennung, endgueltig.kennung} == {BEISPIEL}


def test_laengere_pfade_gewinnen_vor_ihren_praefixen() -> None:
    """`/templates/{id}/prompt` darf nicht als `/templates/{id}` durchgehen."""
    prompt = audit.deuten("PUT", f"/api/v1/templates/{BEISPIEL}/prompt")
    vorlage = audit.deuten("PUT", f"/api/v1/templates/{BEISPIEL}")
    assert prompt is not None and prompt.aktion == "template.prompt_update"
    assert vorlage is not None and vorlage.aktion == "template.update"

    entetikettieren = audit.deuten("DELETE", f"/api/v1/meetings/{BEISPIEL}/tags/{uuid4()}")
    assert entetikettieren is not None
    assert entetikettieren.aktion == "meeting.untag"
    assert entetikettieren.kennung == BEISPIEL


def test_ausleitung_ist_als_solche_erkennbar() -> None:
    """Die Teilmenge, nach der ein Datenschutzbeauftragter fragt."""
    assert "meeting.dispatch" in audit.AUSLEITUNG
    assert "external.export_markdown" in audit.AUSLEITUNG
    assert "archive.ask" in audit.AUSLEITUNG
    # Rein örtliche Vorgänge gehören nicht dazu.
    assert "meeting.delete" not in audit.AUSLEITUNG
    assert "tag.create" not in audit.AUSLEITUNG


def test_ausleitung_nennt_nur_aktionen_die_es_gibt() -> None:
    """Ein Tippfehler in AUSLEITUNG würde den Filter still leer lassen."""
    unbekannt = audit.AUSLEITUNG - set(audit.AKTIONEN)
    assert not unbekannt, f"AUSLEITUNG nennt unbekannte Aktion(en): {sorted(unbekannt)}"


def test_externe_schnittstelle_wird_protokolliert_obwohl_sie_nur_liest() -> None:
    """Lesen ja — aber hier verlassen die Daten die Box.

    Das ist die Ausnahme von der Regel oben: die Aufrufe sind GET, und
    genau sie sind der Weg nach draußen.
    """
    for pfad, erwartet in [
        ("/api/external/v1/meetings", "external.list_meetings"),
        (f"/api/external/v1/meetings/{BEISPIEL}", "external.read_meeting"),
        (f"/api/external/v1/meetings/{BEISPIEL}/markdown", "external.export_markdown"),
    ]:
        vorgang = audit.deuten("GET", pfad)
        assert vorgang is not None, pfad
        assert vorgang.aktion == erwartet


def test_jeder_schreibende_endpunkt_wird_gedeutet() -> None:
    """Kein schreibender Endpunkt ohne Protokollregel.

    Das ist die eigentliche Zusage des Middleware-Musters: die Erfassung
    kann nicht an einer Stelle vergessen werden. Wer einen Endpunkt
    hinzufügt und die Regel vergisst, sieht es hier — nicht erst, wenn
    jemand das Protokoll nach genau diesem Vorgang durchsucht.
    """
    import app.main as hauptmodul

    def beispielpfad(pfad: str) -> str:
        # {cluster_idx} ist eine Zahl, alles andere eine Kennung.
        pfad = re.sub(r"\{[a-z_]*idx\}", "0", pfad)
        return re.sub(r"\{[a-z_]+\}", str(uuid4()), pfad)

    ungedeutet: list[str] = []
    for route in hauptmodul.app.routes:
        methoden = getattr(route, "methods", None)
        if not methoden:
            continue
        pfad = route.path
        if not pfad.startswith(("/api/v1/", "/api/external/v1/")):
            continue
        for methode in methoden & {"POST", "PUT", "PATCH", "DELETE"}:
            if audit.deuten(methode, beispielpfad(pfad)) is None:
                ungedeutet.append(f"{methode} {pfad}")

    assert not ungedeutet, (
        "Schreibende Endpunkte ohne Regel in audit._REGELN: " + ", ".join(sorted(ungedeutet))
    )


# ---------------------------------------------------------------------------
# Urheber und Nachträge
# ---------------------------------------------------------------------------


def test_urheber_ueberlebt_den_weg_zur_middleware() -> None:
    """Hinterlegt wird im ASGI-scope, nicht in einer ContextVar.

    Eine ContextVar, die im Endpunkt gesetzt wird, ist in der Middleware
    nicht mehr zu sehen: Starlette führt den nachgelagerten Aufruf in
    einer eigenen Task aus. Der scope ist dagegen dasselbe Wörterbuch.
    """
    scope: dict = {"method": "DELETE", "path": "/api/v1/meetings/x"}
    audit.merke_akteur(scope, user_id=BEISPIEL, org_id=BEISPIEL, olares_user="kaivostudio")
    abgelegt = scope[audit._SCOPE_SCHLUESSEL]
    assert abgelegt["olares_user"] == "kaivostudio"
    assert abgelegt["user_id"] == BEISPIEL


def test_nachtrag_ergaenzt_was_der_pfad_nicht_hergibt() -> None:
    """Die Kennung einer neuen Besprechung entsteht erst in der Antwort."""
    scope: dict = {}
    neue = uuid4()
    audit.ergaenze(scope, kennung=neue, zusatz={"titel": "Mandantengespräch"})
    audit.ergaenze(scope, zusatz={"dauer": 42})
    abgelegt = scope[audit._SCOPE_SCHLUESSEL]
    assert abgelegt["kennung"] == neue
    # Zwei Nachträge addieren sich, der zweite verwirft den ersten nicht.
    assert abgelegt["zusatz"] == {"titel": "Mandantengespräch", "dauer": 42}


def test_urheber_wird_nachgeschlagen_wenn_der_auth_weg_nicht_lief() -> None:
    """Sonst ist der Eintrag für niemanden sichtbar.

    Scheitert eine Anfrage an der Eingabeprüfung, ruft FastAPI den
    Endpunkt nie auf — `get_current_user` legt den Urheber dann nicht ab.
    Ohne Organisation fällt der Eintrag aus der Ansicht heraus, die nach
    Organisation filtert. Beim Prüflauf am 5.9. war genau eine Zeile so
    verschwunden (`archive.ask`, HTTP 400).
    """
    import asyncio

    class DB:
        async def fetchrow(self, _sql, name):
            assert name == "kaivostudio"
            return {"user_id": BEISPIEL, "org_id": BEISPIEL}

    scope: dict = {}
    asyncio.run(audit.akteur_nachschlagen(DB(), scope, {"x-bfl-user": "kaivostudio"}))
    abgelegt = scope[audit._SCOPE_SCHLUESSEL]
    assert abgelegt["org_id"] == BEISPIEL
    assert abgelegt["olares_user"] == "kaivostudio"


def test_nachschlagen_legt_niemanden_an() -> None:
    """Nur `select`. Anlegen darf allein der Auth-Weg.

    Ein unbekannter Name bekommt seinen Eintrag mit Namen, aber ohne
    Kennung — ein Protokoll ist kein Grund, einen Benutzer zu erzeugen.
    """
    import asyncio

    class UnbekannteDB:
        async def fetchrow(self, _sql, _name):
            return None

    scope: dict = {}
    asyncio.run(audit.akteur_nachschlagen(UnbekannteDB(), scope, {"x-bfl-user": "fremd"}))
    abgelegt = scope[audit._SCOPE_SCHLUESSEL]
    assert abgelegt["olares_user"] == "fremd"
    assert abgelegt.get("org_id") is None


def test_nachschlagen_ueberschreibt_keinen_bekannten_urheber() -> None:
    """Der Auth-Weg weiß es besser — insbesondere beim Zugriffsschlüssel,
    der gar keinen X-Bfl-User-Kopf mitbringt."""
    import asyncio

    class DarfNicht:
        async def fetchrow(self, *_a):
            raise AssertionError("es steht bereits ein Urheber fest")

    scope: dict = {}
    audit.merke_akteur(scope, org_id=BEISPIEL, api_key_id=BEISPIEL)
    asyncio.run(audit.akteur_nachschlagen(DarfNicht(), scope, {"x-bfl-user": "egal"}))
    assert scope[audit._SCOPE_SCHLUESSEL]["api_key_id"] == BEISPIEL


def test_ohne_nachtrag_bleibt_der_eintrag_trotzdem_stehen() -> None:
    """Wer `ergaenze` vergisst, verliert einen Nachtrag, nie den Eintrag."""
    scope: dict = {}
    vorgang = audit.deuten("POST", "/api/v1/recordings")
    assert vorgang is not None
    assert scope.get(audit._SCOPE_SCHLUESSEL) is None
    assert vorgang.aktion == "meeting.create"


# ---------------------------------------------------------------------------
# Herkunft
# ---------------------------------------------------------------------------


def test_herkunft_liest_hinter_envoy_den_weitergabe_kopf() -> None:
    """Die Adresse des Sidecars hilft niemandem."""
    assert audit._herkunft({"x-forwarded-for": "10.0.0.9, 10.0.0.1"}, "127.0.0.1") == "10.0.0.9"


def test_unbrauchbare_herkunft_verhindert_den_eintrag_nicht() -> None:
    """Die Spalte ist `inet` — ein frei gewählter Kopfwert würde den
    Einfügevorgang scheitern lassen. Ausgerechnet den, der interessiert."""
    assert audit._herkunft({"x-forwarded-for": "kein-ip; drop table"}, None) is None
    assert audit._herkunft({}, "auch keine") is None
    assert audit._herkunft({}, "192.168.1.17") == "192.168.1.17"


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------


def test_keine_spalten_die_migrationen_entfernt_haben() -> None:
    """Dieselbe Falle wie beim Konfigurations-Abzug (HANDOFF, v0.1.81).

    Ein Insert gegen eine gedroppte Spalte scheitert bei *jedem* Versuch,
    und weil die Middleware ihre Fehler abfängt, fiele es nur im
    Protokoll der Anwendung auf — nicht im Protokoll, um das es geht.
    """
    wurzel = Path(__file__).resolve().parents[2]
    quelle = (wurzel / "backend/app/audit.py").read_text(encoding="utf-8")

    entfernt: set[str] = set()
    for sql in sorted((wurzel / "supabase/migrations").glob("*.sql")):
        entfernt |= set(
            re.findall(
                r"drop\s+column\s+(?:if\s+exists\s+)?([a-z_]+)",
                sql.read_text(encoding="utf-8"),
                re.IGNORECASE,
            )
        )

    assert entfernt, "keine gedroppten Spalten gefunden — Test prüft nichts"
    genannt = {s for s in entfernt if re.search(rf"\b{re.escape(s)}\b", quelle)}
    assert not genannt, f"Protokoll nennt entfernte Spalte(n): {sorted(genannt)}"


def test_protokoll_spalten_gibt_es_wirklich() -> None:
    """Die Spalten, in die geschrieben wird, müssen angelegt sein.

    `api_key_id` kommt erst mit Migration 0016 dazu — ohne sie schlägt
    jeder Eintrag über die externe Schnittstelle fehl.
    """
    wurzel = Path(__file__).resolve().parents[2]
    migrationen = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((wurzel / "supabase/migrations").glob("*.sql"))
    )
    for spalte in (
        "olares_user",
        "api_key_id",
        "resource_type",
        "resource_id",
        "ip_address",
        "user_agent",
    ):
        assert re.search(rf"\b{spalte}\b", migrationen), f"{spalte} wird nirgends angelegt"
