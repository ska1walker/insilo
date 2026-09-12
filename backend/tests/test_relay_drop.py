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
