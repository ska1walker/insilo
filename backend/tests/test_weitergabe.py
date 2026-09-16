"""Welche Besprechungen ein CRM übernimmt.

Anlass (0.1.102): Beacon übernahm alles aus dem gemeinsamen Ordner —
Kundengespräche, aber auch interne Runden und Sprachnotizen. Filtern
konnte Beacon nur am Namen der Vorlage, und der ist pro Organisation
umbenennbar. Jetzt legt Insilo an der Vorlage fest, was ins CRM geht, und
schreibt es als `crm: true|false` in die Datei und in den Webhook.

Was hier festgehalten wird:

1. Die Voreinstellungen im Saatgut: Mandanten-, Vertriebs- und
   Jahresgespräch ja; Allgemeine Besprechung und Schnellnotiz nein.
2. Wirksam ist die Abweichung der Organisation, sonst die Voreinstellung,
   ohne Vorlage nein.
3. Die Markierung steht in der Datei und im Webhook, und sie lässt sich
   aus der Datei zurücklesen — dafür, dass der nächtliche Abgleich
   veraltete Dateien findet.
4. Umschalten dürfen nur Inhaber und Verwaltende, und es zieht die Dateien
   sofort nach.
"""

from __future__ import annotations

import inspect
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app import relay_drop, weitergabe
from app.config import settings

WURZEL = Path(__file__).resolve().parents[2]
BESPRECHUNG = UUID("d0000000-0000-4000-8000-0000000000c1")
ORG = UUID("00000000-0000-0000-0000-0000000000aa")
NUTZER = UUID("00000000-0000-0000-0000-0000000000bb")
VERTRIEB = UUID("00000000-0000-0000-0000-000000000003")


# ---------------------------------------------------------------------------
# 1. Voreinstellungen im Saatgut
# ---------------------------------------------------------------------------


def _voreinstellungen() -> dict[str, bool]:
    """Name → an_crm, so wie das Saatgut sie schreibt."""
    seed = (WURZEL / "supabase/seed.sql").read_text(encoding="utf-8")
    kopf = seed.index("values", seed.index("insert into public.templates"))
    ergebnis: dict[str, bool] = {}
    for treffer in re.finditer(
        r"\(\s*'(0{8}-0{4}-0{4}-0{4}-0{11}\d)',\s*null,\s*'([^']+)'", seed[kopf:]
    ):
        rest = seed[kopf + treffer.end():]
        ende = re.search(r"\n  (true|false)\n\)", rest)
        assert ende, f"Vorlage {treffer.group(2)} ohne an_crm am Ende"
        ergebnis[treffer.group(2)] = ende.group(1) == "true"
    return ergebnis


def test_kundengespraeche_gehen_ins_crm() -> None:
    werte = _voreinstellungen()
    assert werte["Mandantengespräch"] is True
    assert werte["Vertriebsgespräch"] is True
    # Im Saatgut ein Kundengespräch („für die Kundenakte", Cross-Selling,
    # Risikoveränderungen) — nicht das Gespräch mit Mitarbeitenden.
    assert werte["Jahresgespräch"] is True


def test_interne_runden_und_notizen_nicht() -> None:
    werte = _voreinstellungen()
    assert werte["Allgemeine Besprechung"] is False
    assert werte["Schnellnotiz"] is False


def test_jede_systemvorlage_hat_eine_voreinstellung() -> None:
    assert len(_voreinstellungen()) == 5


def test_das_saatgut_zieht_die_voreinstellung_nach() -> None:
    """Sonst bekämen bestehende Installationen die Voreinstellung nie.

    Die Migration kann sie nicht setzen: sie läuft vor dem Saatgut, und
    auf einer frischen Installation gäbe es noch keine Zeile.
    """
    seed = (WURZEL / "supabase/seed.sql").read_text(encoding="utf-8")
    assert "an_crm           = excluded.an_crm" in seed
    migration = (WURZEL / "supabase/migrations/0021_weitergabe_crm.sql").read_text(encoding="utf-8")
    assert "update public.templates" not in migration


def test_die_abweichung_liegt_nicht_in_den_anpassungen() -> None:
    """„Zurücksetzen" am Prompt löscht die Anpassungszeile.

    Stünde die Markierung dort, änderte sich nebenbei, was ins CRM geht.
    """
    migration = (WURZEL / "supabase/migrations/0021_weitergabe_crm.sql").read_text(encoding="utf-8")
    assert "create table if not exists public.template_weitergabe" in migration
    assert "template_customizations\n  add column" not in migration


def test_die_tabelle_ist_abgesichert() -> None:
    migration = (WURZEL / "supabase/migrations/0021_weitergabe_crm.sql").read_text(encoding="utf-8")
    assert "alter table public.template_weitergabe force row level security" in migration
    assert "current_user_role_in_org(org_id) in ('owner', 'admin')" in migration
    assert "public.ist_dienst()" in migration


# ---------------------------------------------------------------------------
# 2. Was wirksam ist
# ---------------------------------------------------------------------------


def test_abweichung_vor_voreinstellung_ohne_vorlage_nein() -> None:
    spalte = " ".join(weitergabe.SPALTE.split())
    assert spalte.startswith("coalesce( (select w.an_crm from public.template_weitergabe w")
    assert "(select t.an_crm from public.templates t where t.id = m.template_id)" in spalte
    assert spalte.endswith("false ) as an_crm")
    # Die Abweichung gilt nur für die eigene Organisation.
    assert "w.org_id = m.org_id" in spalte


class _Vorlage:
    def __init__(self, zeile):
        self.zeile = zeile

    async def fetchrow(self, _sql, *_args):
        return self.zeile


@pytest.mark.parametrize(
    ("voreinstellung", "abweichung", "wirksam", "weicht_ab"),
    [
        (True, None, True, False),
        (False, None, False, False),
        (True, False, False, True),
        (False, True, True, True),
    ],
)
async def test_fuer_vorlage(voreinstellung, abweichung, wirksam, weicht_ab) -> None:
    ergebnis = await weitergabe.fuer_vorlage(
        _Vorlage({"voreinstellung": voreinstellung, "abweichung": abweichung}), ORG, VERTRIEB
    )
    assert ergebnis == (wirksam, voreinstellung, weicht_ab)


async def test_unbekannte_vorlage_geht_nicht_ins_crm() -> None:
    assert await weitergabe.fuer_vorlage(_Vorlage(None), ORG, VERTRIEB) == (False, False, False)


# ---------------------------------------------------------------------------
# 3. In der Datei und im Webhook
# ---------------------------------------------------------------------------


class _Einsammeln:
    """Die Abfragen aus `ablage._einsammeln`, mit wählbarer Markierung."""

    def __init__(self, an_crm: bool, vorlage: str = "Vertriebsgespräch") -> None:
        self.an_crm = an_crm
        self.vorlage = vorlage

    async def fetchrow(self, sql: str, *_args):
        if "from public.meetings m" in sql:
            return {
                "id": BESPRECHUNG,
                "org_id": ORG,
                "title": "Termin Musterbau",
                "recorded_at": datetime(2026, 9, 16, 9, 0, tzinfo=UTC),
                "duration_sec": 1800,
                "language": "de",
                "template_name": self.vorlage,
                "an_crm": self.an_crm,
            }
        if "from public.transcripts" in sql:
            return {"segments": [], "speakers": [], "full_text": "", "language": "de"}
        if "from public.summaries" in sql:
            return {"content": {"zusammenfassung": "Kurz."}, "llm_model": "m"}
        raise AssertionError(sql)

    async def fetch(self, _sql: str, *_args):
        return []


@pytest.fixture
def exportdir(tmp_path, monkeypatch):
    ziel = tmp_path / "insilo-meetings"
    ziel.mkdir()
    monkeypatch.setattr(settings, "meeting_export_dir", str(ziel))
    return ziel


def _kopf(text: str) -> dict[str, str]:
    zeilen = text.splitlines()
    ende = zeilen.index("---", 1)
    return dict(z.partition(": ")[::2] for z in zeilen[1:ende])


@pytest.mark.parametrize("an_crm", [True, False])
async def test_die_markierung_steht_in_der_datei(exportdir, an_crm: bool) -> None:
    name = await relay_drop.schreiben(_Einsammeln(an_crm), BESPRECHUNG)
    kopf = _kopf((exportdir / name).read_text(encoding="utf-8"))
    assert kopf["crm"] == ("true" if an_crm else "false")
    # Weiterhin schema 1: ein zusätzlicher Schlüssel, den ältere Leser überlesen.
    assert kopf["schema"] == "1"


async def test_auch_eine_umbenannte_vorlage_behaelt_die_markierung(exportdir) -> None:
    """Der Grund, warum nicht am Namen gefiltert wird."""
    name = await relay_drop.schreiben(_Einsammeln(True, vorlage="Kundentermin"), BESPRECHUNG)
    assert _kopf((exportdir / name).read_text(encoding="utf-8"))["crm"] == "true"


async def test_die_markierung_laesst_sich_zuruecklesen(exportdir) -> None:
    await relay_drop.schreiben(_Einsammeln(False), BESPRECHUNG)
    assert relay_drop.crm_markierung(BESPRECHUNG) is False
    await relay_drop.schreiben(_Einsammeln(True), BESPRECHUNG)
    assert relay_drop.crm_markierung(BESPRECHUNG) is True


async def test_veraltet_erkennt_umgestellte_vorlagen(exportdir) -> None:
    await relay_drop.schreiben(_Einsammeln(True), BESPRECHUNG)
    assert relay_drop.veraltet(BESPRECHUNG, True) is False
    assert relay_drop.veraltet(BESPRECHUNG, False) is True


def test_eine_datei_ohne_schluessel_gilt_als_veraltet(exportdir) -> None:
    """Geschrieben vor 0.1.102: muss einmal neu, sonst bleibt Beacon ungefiltert."""
    (exportdir / f"2026-09-01T08_00--{str(BESPRECHUNG)[:8]}.md").write_text(
        f'---\ninsilo_id: "{BESPRECHUNG}"\ntemplate: "Allgemeine Besprechung"\n'
        "source_url: ''\nschema: 1\n---\n---\nsource: insilo\n---\n# Alt\n",
        encoding="utf-8",
    )
    assert relay_drop.crm_markierung(BESPRECHUNG) is None
    assert relay_drop.veraltet(BESPRECHUNG, False) is True


def test_ohne_datei_ist_nichts_veraltet(exportdir) -> None:
    """Keine Datei ist ein Fall für `fehlt`, nicht für `veraltet`."""
    assert relay_drop.veraltet(BESPRECHUNG, True) is False


def test_nur_der_kopf_wird_gelesen(exportdir) -> None:
    """Insilos Markdown hinter dem Kopf hat einen eigenen Kopf — der zählt nicht."""
    (exportdir / f"2026-09-01T08_00--{str(BESPRECHUNG)[:8]}.md").write_text(
        f'---\ninsilo_id: "{BESPRECHUNG}"\nschema: 1\n---\n---\ncrm: true\n---\n',
        encoding="utf-8",
    )
    assert relay_drop.crm_markierung(BESPRECHUNG) is None


def test_der_webhook_traegt_die_markierung() -> None:
    from app.tasks import notify

    quelle = " ".join(inspect.getsource(notify).split())
    assert '"crm": bool(meeting["an_crm"])' in quelle
    assert "weitergabe.SPALTE" in quelle


def test_der_naechtliche_abgleich_schreibt_veraltetes_neu() -> None:
    from app.tasks import aufraeumen

    quelle = " ".join(inspect.getsource(aufraeumen._markdown_nachziehen).split())
    assert 'relay_drop.veraltet(zeile["id"], bool(zeile["an_crm"]))' in quelle


# ---------------------------------------------------------------------------
# 4. Umschalten
# ---------------------------------------------------------------------------


class _Schalter:
    def __init__(self, rolle: str, voreinstellung: bool, vorlage_da: bool = True) -> None:
        self.rolle = rolle
        self.voreinstellung = voreinstellung
        self.vorlage_da = vorlage_da
        self.ausgefuehrt: list[tuple[str, tuple]] = []

    async def fetchval(self, sql: str, *_args):
        if "user_org_roles" in sql:
            return self.rolle
        if "from public.templates" in sql:
            return 1 if self.vorlage_da else None
        raise AssertionError(sql)

    async def fetchrow(self, _sql: str, *_args):
        return {"voreinstellung": self.voreinstellung, "abweichung": None}

    async def execute(self, sql: str, *args):
        self.ausgefuehrt.append((" ".join(sql.split()), args))


@pytest.fixture
def schalten(monkeypatch: pytest.MonkeyPatch):
    from app import main, worker
    from app.auth import CurrentUser, get_current_user
    from app.routers import templates

    zustand: dict = {"verbindung": None, "gesendet": []}

    @asynccontextmanager
    async def _acquire_as(_user_id):
        yield zustand["verbindung"]

    monkeypatch.setattr(settings, "internal_token", "")
    monkeypatch.setattr(templates, "acquire_as", _acquire_as)

    class _App:
        @staticmethod
        def send_task(name, args=None, **_kw):
            zustand["gesendet"].append((name, list(args or [])))

    monkeypatch.setattr(worker, "celery_app", _App)

    async def _nutzer() -> CurrentUser:
        return CurrentUser(user_id=NUTZER, org_id=ORG, olares_username="kai")

    main.app.dependency_overrides[get_current_user] = _nutzer
    yield TestClient(main.app, raise_server_exceptions=False), zustand
    main.app.dependency_overrides.clear()


def _setzen(k: TestClient, an_crm: bool):
    return k.put(f"/api/v1/templates/{VERTRIEB}/weitergabe", json={"an_crm": an_crm})


@pytest.mark.parametrize("rolle", ["member", "viewer", None])
def test_nur_inhaber_und_verwaltende_duerfen(schalten, rolle) -> None:
    k, zustand = schalten
    zustand["verbindung"] = _Schalter(rolle, voreinstellung=True)

    antwort = _setzen(k, False)

    assert antwort.status_code == 403
    assert "Inhaberinnen und Verwaltende" in antwort.json()["detail"]
    assert zustand["verbindung"].ausgefuehrt == []
    assert zustand["gesendet"] == []


def test_abweichung_wird_gespeichert_und_nachgezogen(schalten) -> None:
    k, zustand = schalten
    zustand["verbindung"] = _Schalter("admin", voreinstellung=True)

    antwort = _setzen(k, False)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json() == {
        "template_id": str(VERTRIEB), "an_crm": False, "an_crm_standard": True,
    }
    [(sql, args)] = zustand["verbindung"].ausgefuehrt
    assert sql.startswith("insert into public.template_weitergabe")
    assert args[2] is False
    assert zustand["gesendet"] == [("weitergabe_nachziehen", [str(ORG), str(VERTRIEB)])]


def test_zurueck_auf_die_voreinstellung_loescht_die_abweichung(schalten) -> None:
    """Sonst bekäme die Organisation spätere Änderungen am Saatgut nicht mit."""
    k, zustand = schalten
    zustand["verbindung"] = _Schalter("owner", voreinstellung=True)

    assert _setzen(k, True).status_code == 200

    [(sql, _args)] = zustand["verbindung"].ausgefuehrt
    assert sql.startswith("delete from public.template_weitergabe")


def test_unbekannte_vorlage(schalten) -> None:
    k, zustand = schalten
    zustand["verbindung"] = _Schalter("owner", voreinstellung=False, vorlage_da=False)

    assert _setzen(k, True).status_code == 404
    assert zustand["gesendet"] == []


def test_warteschlange_weg_laesst_die_einstellung_stehen(schalten, monkeypatch) -> None:
    """Das nächtliche Aufräumen gleicht die Dateien ohnehin ab."""
    from app import worker

    k, zustand = schalten
    zustand["verbindung"] = _Schalter("owner", voreinstellung=True)

    class _Weg:
        @staticmethod
        def send_task(*_a, **_k):
            raise RuntimeError("Warteschlange weg")

    monkeypatch.setattr(worker, "celery_app", _Weg)

    assert _setzen(k, False).status_code == 200
    assert zustand["verbindung"].ausgefuehrt, "die Einstellung wurde trotzdem gespeichert"
