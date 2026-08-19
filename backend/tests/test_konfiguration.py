"""Prüft den Konfigurations-Abzug neben dem Audio.

Der Anlass steht in app/konfiguration.py: eine Neuinstallation legt die
Olares-Datenbank neu an, `/app/data` überlebt. Ohne Abzug bekommt die
Organisation dabei eine neue Kennung — und die Aufnahmen unter
`audio/<org-id>/` gehören dann zu niemandem mehr.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import konfiguration


def test_abzug_liegt_neben_dem_audio() -> None:
    """Neben `audio/`, nicht darin — dort gehören die Aufnahmen hin."""
    assert konfiguration.DATEI.name == "konfiguration.json"
    assert konfiguration.DATEI.parent.name != "audio"


def test_uuid_und_datum_werden_serialisierbar() -> None:
    from datetime import datetime
    from uuid import UUID

    assert konfiguration._j(UUID("8ecf16a0-ebc5-4365-b72e-51f13830e57c")) == (
        "8ecf16a0-ebc5-4365-b72e-51f13830e57c"
    )
    assert konfiguration._j(datetime(2026, 8, 19, 11, 48)).startswith("2026-08-19T11:48")
    assert konfiguration._j("unverändert") == "unverändert"
    assert konfiguration._j(None) is None


def test_schema_wird_geprueft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Abzug aus einer künftigen Fassung wird übersprungen statt geraten.

    Halb eingelesene Konfiguration wäre schlimmer als gar keine: der Nutzer
    sähe eine App, die teils eingerichtet aussieht.
    """
    datei = tmp_path / "konfiguration.json"
    datei.write_text(json.dumps({"schema": konfiguration.SCHEMA + 1, "org": {"id": "x"}}))
    monkeypatch.setattr(konfiguration, "DATEI", datei)

    import asyncio

    class LeereDB:
        async def fetchval(self, *_a, **_k):
            return 0

    assert asyncio.run(konfiguration.wiederherstellen(LeereDB())) is False


def test_volle_datenbank_wird_nicht_ueberschrieben(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Datenbank ist die Wahrheit. Ein alter Abzug darf laufende
    Einstellungen nicht überschreiben — gelesen wird nur ins Leere."""
    datei = tmp_path / "konfiguration.json"
    datei.write_text(json.dumps({"schema": konfiguration.SCHEMA, "org": {"id": "x"}}))
    monkeypatch.setattr(konfiguration, "DATEI", datei)

    import asyncio

    class VolleDB:
        async def fetchval(self, *_a, **_k):
            return 1

    assert asyncio.run(konfiguration.wiederherstellen(VolleDB())) is False


def test_ohne_datei_passiert_nichts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(konfiguration, "DATEI", tmp_path / "gibtsnicht.json")
    import asyncio

    class DB:
        async def fetchval(self, *_a, **_k):
            raise AssertionError("darf gar nicht erst gefragt werden")

    assert asyncio.run(konfiguration.wiederherstellen(DB())) is False


def test_pfad_haengt_nicht_an_app_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """`APP_DATA_DIR` trägt auf Olares den Host-Pfad — der Abzug darf nicht daran hängen.

    Das Deployment setzt `APP_DATA_DIR` auf `.Values.userspace.appData`, also
    auf den Pfad, unter dem das Volume auf dem *Knoten* liegt
    (`/olares/rootfs/userspace/pvc-.../Data/insilo`). Im Container gibt es
    den nicht. In v0.1.80 zeigte der Abzug deshalb ins Leere; er landete nie
    auf der Platte. Maßgeblich ist, wo das Audio liegt.
    """
    import importlib

    from app.config import settings

    monkeypatch.setenv("APP_DATA_DIR", "/olares/rootfs/userspace/pvc-irgendwas/Data/insilo")
    neu = importlib.reload(konfiguration)
    try:
        assert neu.DATEI.parent == Path(settings.storage_local_path).parent
        assert "/olares/rootfs" not in str(neu.DATEI)
    finally:
        monkeypatch.delenv("APP_DATA_DIR", raising=False)
        importlib.reload(konfiguration)


def test_keine_spalten_die_migrationen_entfernt_haben() -> None:
    """Das SQL hier darf keine Spalte nennen, die eine Migration gedroppt hat.

    v0.1.80 fragte `template_customizations.system_prompt` ab — Migration
    0013 hatte die Spalte entfernt, seither heißt sie `system_prompts`
    (JSONB). Der Abzug scheiterte damit bei *jedem* Versuch, und weil er
    seine Fehler schluckt, fiel es nur im Protokoll auf.
    """
    import re

    wurzel = Path(__file__).resolve().parents[2]
    quelle = (wurzel / "backend/app/konfiguration.py").read_text(encoding="utf-8")

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
    assert not genannt, f"Abzug nennt entfernte Spalte(n): {sorted(genannt)}"
