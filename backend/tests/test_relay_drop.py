"""Prüft die Relay-Kopie der Zusammenfassungen im gemeinsamen Verzeichnis.

Die Ablage legt das Markdown in den Insilo-eigenen Speicher; Relay sieht
den nicht. `relay_drop` schreibt dieselbe Zusammenfassung zusätzlich in
ein Verzeichnis, das beide Apps sehen. Was hier als Test steht:

1. Die Datei **kommt**, sobald es eine Zusammenfassung gibt — atomar,
   deterministisch benannt, mit einer Frontmatter, die Relay ohne
   YAML-Lib parst.
2. Die Datei **geht**, wenn die Besprechung endgültig verschwindet.
3. Ohne gesetztes Verzeichnis ist alles stumm — der Export ist eine
   Bequemlichkeit, keine Bedingung.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app import relay_drop
from app.config import settings

BESPRECHUNG = UUID("d0000000-0000-4000-8000-000000000001")
ZEIT = datetime(2026, 9, 12, 14, 30, tzinfo=UTC)
SPRECHER = [{"id": "s1", "name": "Dr. Beispiel"}, {"id": "s2", "name": "Herr Muster"}]
INHALT = {
    "kernthemen": ["Nachtragsforderung"],
    "naechste_schritte": [
        {"aufgabe": "Angebot erstellen", "verantwortlich": "Herr Muster", "frist": "2026-09-20"}
    ],
}


class Verbindung:
    """Liefert die vier Abfragen aus `ablage._einsammeln` — ohne Datenbank."""

    def __init__(self, *, zusammenfassung: bool = True, besprechung: bool = True) -> None:
        self.zusammenfassung = zusammenfassung
        self.besprechung = besprechung

    async def fetchrow(self, sql: str, *args):
        if "from public.meetings m" in sql:
            if not self.besprechung:
                return None
            return {
                "id": BESPRECHUNG,
                "org_id": UUID("11111111-1111-4111-8111-111111111111"),
                "title": "Mandantengespräch Musterbau GmbH",
                "recorded_at": ZEIT,
                "duration_sec": 1847,
                "language": "de",
                "template_name": "Mandantengespräch",
            }
        if "from public.transcripts" in sql:
            return {
                "segments": [],
                "speakers": SPRECHER,
                "full_text": "Guten Morgen.",
                "language": "de",
            }
        if "from public.summaries" in sql:
            if not self.zusammenfassung:
                return None
            return {"content": INHALT, "llm_model": "qwen2.5"}
        raise AssertionError(f"unerwartetes fetchrow: {sql!r}")

    async def fetch(self, sql: str, *args):
        if "from public.meeting_tags" in sql:
            return [{"name": "Mandat 2026-014", "color": "#caa960"}]
        raise AssertionError(f"unerwartetes fetch: {sql!r}")


@pytest.fixture
def exportdir(tmp_path, monkeypatch):
    """Leeres Drop-Verzeichnis, das der Export kennt."""
    ziel = tmp_path / "insilo-meetings"
    ziel.mkdir()
    monkeypatch.setattr(settings, "meeting_export_dir", str(ziel))
    return ziel


def _frontmatter_teile(text: str) -> dict[str, str]:
    """Die Frontmatter so zerlegen, wie Relay es tut: Zeile für Zeile."""
    zeilen = text.splitlines()
    assert zeilen[0] == "---"
    ende = zeilen.index("---", 1)
    teile: dict[str, str] = {}
    for zeile in zeilen[1:ende]:
        schlüssel, _, wert = zeile.partition(": ")
        teile[schlüssel] = wert
    return teile


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------


async def test_datei_kommt_mit_zusammenfassung(exportdir) -> None:
    name = await relay_drop.schreiben(Verbindung(), BESPRECHUNG)
    assert name == "2026-09-12T14_30--d0000000.md"
    datei = exportdir / name
    assert datei.exists()
    text = datei.read_text(encoding="utf-8")
    teile = _frontmatter_teile(text)
    assert teile["insilo_id"] == f'"{BESPRECHUNG}"'
    assert teile["title"] == '"Mandantengespräch Musterbau GmbH"'
    assert teile["schema"] == "1"
    # Teilnehmer und Etiketten sind JSON-Arrays — Relay parst sie ohne YAML.
    assert json.loads(teile["participants"]) == ["Dr. Beispiel", "Herr Muster"]
    assert json.loads(teile["tags"]) == ["Mandat 2026-014"]
    # Der Body trägt die kanonische Überschrift, aber kein Transkript.
    assert "# Mandantengespräch Musterbau GmbH" in text
    assert "Guten Morgen." not in text.split("---", 2)[2]


async def test_schreiben_ist_idempotent_und_aktualisiert(exportdir) -> None:
    name = await relay_drop.schreiben(Verbindung(), BESPRECHUNG)
    alter_inhalt = (exportdir / name).read_bytes()
    # Zweiter Lauf: gleiche Datei, kein drittes File, kein .tmp-Rest.
    assert await relay_drop.schreiben(Verbindung(), BESPRECHUNG) == name
    assert (exportdir / name).read_bytes() == alter_inhalt
    assert [d.name for d in exportdir.iterdir()] == [name]


async def test_ohne_zusammenfassung_keine_datei(exportdir) -> None:
    assert await relay_drop.schreiben(Verbindung(zusammenfassung=False), BESPRECHUNG) is None
    assert list(exportdir.iterdir()) == []


async def test_ohne_besprechungszeile_keine_datei(exportdir) -> None:
    assert await relay_drop.schreiben(Verbindung(besprechung=False), BESPRECHUNG) is None
    assert list(exportdir.iterdir()) == []


async def test_deaktiviert_wenn_verzeichnis_leer(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "meeting_export_dir", "")
    assert await relay_drop.schreiben(Verbindung(), BESPRECHUNG) is None
    assert relay_drop.fehlt(BESPRECHUNG) is False


async def test_atomar_kein_tmp_rest(exportdir) -> None:
    await relay_drop.schreiben(Verbindung(), BESPRECHUNG)
    assert not any(d.name.endswith(".tmp") for d in exportdir.iterdir())


async def test_dateiname_ist_ascii_obwohl_titel_umlaute_hat(exportdir) -> None:
    name = await relay_drop.schreiben(Verbindung(), BESPRECHUNG)
    assert name.isascii()


# ---------------------------------------------------------------------------
# Entfernen und Nachzug
# ---------------------------------------------------------------------------


async def test_entfernen_holt_die_datei_weg(exportdir) -> None:
    await relay_drop.schreiben(Verbindung(), BESPRECHUNG)
    assert relay_drop.entfernen(BESPRECHUNG) is True
    assert list(exportdir.iterdir()) == []


async def test_entfernen_ohne_datei_ist_kein_fehler(exportdir) -> None:
    assert relay_drop.entfernen(BESPRECHUNG) is True


async def test_fehlt_erkennt_nachzugbedarf(exportdir) -> None:
    assert relay_drop.fehlt(BESPRECHUNG) is True
    await relay_drop.schreiben(Verbindung(), BESPRECHUNG)
    assert relay_drop.fehlt(BESPRECHUNG) is False


# ---------------------------------------------------------------------------
# Zwei Besprechungen mit denselben acht Anfangszeichen
# ---------------------------------------------------------------------------


def _datei_fuer(verzeichnis, kennung, stunde: int) -> None:
    import datetime as dt

    name = relay_drop.dateiname(
        {"id": kennung, "recorded_at": dt.datetime(2026, 9, 1, stunde, 0, tzinfo=dt.UTC)}
    )
    (verzeichnis / name).write_text(f'---\ninsilo_id: "{kennung}"\n---\n', encoding="utf-8")


A = UUID("7dac31c7-0000-4000-8000-00000000000a")
B = UUID("7dac31c7-ffff-4fff-8fff-ffffffffffff")


def test_entfernen_trifft_nicht_die_nachbarin(exportdir) -> None:
    """Gefunden im Review von PR #1, vorgeführt vor dem Fix.

    Der Dateiname führt nur acht Zeichen der Kennung, und `entfernen`
    suchte nach genau diesen acht. Wer Besprechung A endgültig löschte,
    löschte damit auch die Exportdatei von B — auf einem Löschpfad, der
    ohnehin unumkehrbar ist.
    """
    _datei_fuer(exportdir, A, 9)
    _datei_fuer(exportdir, B, 14)

    assert relay_drop.entfernen(A) is True

    uebrig = sorted(p.name for p in exportdir.iterdir())
    assert len(uebrig) == 1, f"B ist mit verschwunden: {uebrig}"
    assert relay_drop.fehlt(A) is True
    assert relay_drop.fehlt(B) is False


def test_fehlt_verwechselt_nicht_die_nachbarin(exportdir) -> None:
    """Liegt nur A's Datei, darf `fehlt(B)` nicht „schon da" melden.

    Sonst bekäme B im nächtlichen Nachzug nie eine Datei.
    """
    _datei_fuer(exportdir, A, 9)
    assert relay_drop.fehlt(A) is False
    assert relay_drop.fehlt(B) is True


# ---------------------------------------------------------------------------
# Was im Review von PR #1 dazukam
# ---------------------------------------------------------------------------


def test_der_export_aller_besprechungen_steht_im_protokoll() -> None:
    """Er legt die Zusammenfassungen einer ganzen Organisation in einen
    Ordner, den andere Apps lesen. Ohne Regel lief er am Protokoll vorbei —
    gefunden hat das `test_jeder_schreibende_endpunkt_wird_gedeutet`, der
    im PR rot war.
    """
    from app import audit

    vorgang = audit.deuten("POST", "/api/v1/meetings/export-backfill")
    assert vorgang is not None
    assert vorgang.aktion == "meeting.export_backfill"
    assert vorgang.aktion in audit.AUSLEITUNG, (
        "der Export gehört zu dem, wonach ein Datenschutzbeauftragter fragt"
    )


def test_den_export_duerfen_nur_inhaber_und_verwaltende() -> None:
    import inspect

    from app.routers.meetings import export_backfill

    quelle = inspect.getsource(export_backfill)
    assert '("owner", "admin")' in quelle
    assert "meeting.export_forbidden" in quelle
    # Die Prüfung muss vor der Abfrage der Besprechungen stehen.
    assert quelle.index("export_forbidden") < quelle.index("from public.meetings")


def test_der_nachweis_zeigt_den_ordner_mit_gezaehlter_anzahl(exportdir) -> None:
    _datei_fuer(exportdir, A, 9)
    _datei_fuer(exportdir, B, 14)
    (exportdir / "halb.md.tmp").write_text("abgebrochen", encoding="utf-8")

    ordner, anzahl = relay_drop.verzeichnis_und_anzahl()
    assert ordner == str(exportdir)
    assert anzahl == 2, "ein .tmp aus einem abgebrochenen Lauf ist keine Freigabe"


def test_ohne_export_kein_eintrag_im_nachweis(tmp_path, monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "meeting_export_dir", "")
    assert relay_drop.verzeichnis_und_anzahl() is None


def test_das_chart_uebernimmt_nicht_den_gemeinsamen_ordner() -> None:
    """`/app/common` gehört allen Apps, die ihn anfordern.

    Der PR setzte bei jedem Start `chown 1000:1000 /app/common` — die
    oberste Stufe eines Ordners, in dem andere Apps mit anderer Kennung
    ihre eigenen Ordner haben. Übernommen werden darf nur der eigene
    Unterordner.
    """
    from pathlib import Path

    wurzel = Path(__file__).resolve().parents[2]
    for datei in ("deployment-backend.yaml", "deployment-worker.yaml"):
        text = (wurzel / "olares/templates" / datei).read_text(encoding="utf-8")
        befehl = next(z for z in text.splitlines() if "command:" in z and "chown" in z)
        assert "chown 1000:1000 /app/common " not in befehl + " ", (
            f"{datei}: der gemeinsame Ordner wird wieder übernommen"
        )
        assert "chown 1000:1000 /app/common/insilo-meetings" in befehl, datei
