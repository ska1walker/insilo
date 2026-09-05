"""Prüft Papierkorb und Aufbewahrungsfristen.

Der Anlass steht in app/tasks/aufraeumen.py: bis v0.1.81 entfernte das
Löschen die Tonaufnahme sofort und unwiderruflich, während `deleted_at`
eine Frist auf eine Zeile setzte, deren Inhalt schon weg war — und
`orgs.audio_retention_days` stand seit Migration 0001 in der Tabelle, ohne
dass eine Zeile Code sie je gelesen hätte.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from app.tasks import aufraeumen

WURZEL = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Die Regression, um die es geht
# ---------------------------------------------------------------------------


def test_loeschen_entfernt_die_tonaufnahme_nicht() -> None:
    """Der Kern der Sache: soft-delete darf die Datei nicht anfassen.

    Vorher stand in `delete_meeting` ein `delete_object(...)` direkt nach
    dem Setzen von `deleted_at`. Wer versehentlich löschte, hatte die
    Aufnahme verloren — der Papierkorb hätte nur eine leere Hülle
    zurückgeben können. Die Datei entfernt jetzt ausschließlich der
    Aufräum-Job nach Ablauf der Frist, oder das ausdrückliche endgültige
    Löschen.
    """
    from app.routers.meetings import delete_meeting

    quelle = inspect.getsource(delete_meeting)
    assert "delete_object" not in quelle, (
        "delete_meeting entfernt wieder die Datei — damit ist der Papierkorb leer"
    )


def test_endgueltig_loeschen_entfernt_die_datei_schon() -> None:
    """Das ist der Weg, auf dem die Datei verschwinden *soll*."""
    from app.routers.meetings import purge_meeting

    assert "delete_object" in inspect.getsource(purge_meeting)


def test_endgueltig_loeschen_geht_nur_aus_dem_papierkorb() -> None:
    """Was nicht gelöscht ist, kann hier nicht verschwinden."""
    from app.routers.meetings import purge_meeting

    assert "deleted_at is not null" in inspect.getsource(purge_meeting)


def test_zurueckholen_geht_nur_bei_geloeschten() -> None:
    """Sonst würde ein zweiter Aufruf eine laufende Besprechung „wiederherstellen"."""
    from app.routers.meetings import restore_meeting

    quelle = inspect.getsource(restore_meeting)
    assert "deleted_at is not null" in quelle
    assert "set deleted_at = null" in quelle


# ---------------------------------------------------------------------------
# Datei entfernen
# ---------------------------------------------------------------------------


def test_speicherfehler_gibt_die_zeile_nicht_frei(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sonst entsteht genau der Zustand vom 19. August.

    Eine Datei ohne Besprechung gehört niemandem mehr — dreizehn davon
    lagen auf der Box und mussten von Hand wieder angehängt werden. Wenn
    der Speicher klemmt, bleibt die Zeile stehen und der nächste Lauf
    versucht es erneut.
    """

    def klemmt(_pfad: str) -> None:
        raise OSError("Nur-Lesen-Dateisystem")

    monkeypatch.setattr(aufraeumen, "delete_object", klemmt)
    assert aufraeumen._datei_weg("org/besprechung.webm") is False


def test_bereits_verschwundene_datei_haelt_nicht_auf(monkeypatch: pytest.MonkeyPatch) -> None:
    def schon_weg(_pfad: str) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(aufraeumen, "delete_object", schon_weg)
    assert aufraeumen._datei_weg("org/besprechung.webm") is True


def test_ohne_datei_ist_nichts_zu_tun(monkeypatch: pytest.MonkeyPatch) -> None:
    def darf_nicht(_pfad: str) -> None:
        raise AssertionError("ohne Pfad gibt es nichts zu entfernen")

    monkeypatch.setattr(aufraeumen, "delete_object", darf_nicht)
    assert aufraeumen._datei_weg(None) is True
    assert aufraeumen._datei_weg("") is True


# ---------------------------------------------------------------------------
# Die beiden Fristen
# ---------------------------------------------------------------------------


def test_aufbewahrungsfrist_trifft_nur_die_aufnahme() -> None:
    """Transkript und Zusammenfassung bleiben — sie sind der Aktenbestandteil.

    Nur die Tonspur ist Rohmaterial. Ein `delete from public.meetings` in
    diesem Zweig würde aus einer Aufbewahrungsfrist eine Löschfrist für
    das Gesprächsprotokoll machen.
    """
    quelle = inspect.getsource(aufraeumen._aufnahmen_altern)
    assert "delete from public.meetings" not in quelle
    assert "audio_deleted_at = now()" in quelle
    # `audio_path` wird geleert, damit jede bestehende Abfrage von selbst
    # „keine Aufnahme" sieht, statt auf eine fehlende Datei zu zeigen.
    assert "audio_path = null" in quelle


def test_null_schaltet_die_aufbewahrungsfrist_ab() -> None:
    """`audio_retention_days = 0` heißt unbegrenzt, nicht „sofort weg"."""
    assert "audio_retention_days > 0" in inspect.getsource(aufraeumen._aufnahmen_altern)


def test_papierkorb_entfernt_die_besprechung_ganz() -> None:
    """Hier — und nur hier — verschwindet die Zeile."""
    quelle = inspect.getsource(aufraeumen._papierkorb_leeren)
    assert "delete from public.meetings" in quelle
    assert "deleted_at is not null" in quelle


def test_fristen_stehen_pro_organisation_in_der_datenbank() -> None:
    """Nicht als Konstante im Code — ein Kunde darf seine Frist setzen."""
    quelle = inspect.getsource(aufraeumen)
    assert "trash_retention_days" in quelle
    assert "audio_retention_days" in quelle
    assert "join public.orgs" in quelle


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_benutzte_spalten_gibt_es_wirklich() -> None:
    migrationen = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((WURZEL / "supabase/migrations").glob("*.sql"))
    )
    for spalte in ("trash_retention_days", "audio_retention_days", "audio_deleted_at"):
        assert re.search(rf"\b{spalte}\b", migrationen), f"{spalte} wird nirgends angelegt"


def test_keine_spalten_die_migrationen_entfernt_haben() -> None:
    quelle = (WURZEL / "backend/app/tasks/aufraeumen.py").read_text(encoding="utf-8")

    entfernt: set[str] = set()
    for sql in sorted((WURZEL / "supabase/migrations").glob("*.sql")):
        entfernt |= set(
            re.findall(
                r"drop\s+column\s+(?:if\s+exists\s+)?([a-z_]+)",
                sql.read_text(encoding="utf-8"),
                re.IGNORECASE,
            )
        )

    assert entfernt, "keine gedroppten Spalten gefunden — Test prüft nichts"
    genannt = {s for s in entfernt if re.search(rf"\b{re.escape(s)}\b", quelle)}
    assert not genannt, f"Aufräum-Job nennt entfernte Spalte(n): {sorted(genannt)}"


def test_der_job_laeuft_taeglich() -> None:
    """Ohne Zeitplan setzt niemand die Fristen durch."""
    from app.worker import celery_app

    plan = celery_app.conf.beat_schedule
    assert "aufraeumen-taeglich" in plan
    assert plan["aufraeumen-taeglich"]["task"] == "aufraeumen"


def test_der_worker_startet_den_zeitplaner_mit() -> None:
    """Der Zeitplan im Code nützt nichts, wenn der Beat nicht läuft.

    Er läuft eingebettet im Worker (`--beat`), nicht als zweites
    Deployment — zulässig bei genau einem Replikat.
    """
    deployment = (WURZEL / "olares/templates/deployment-worker.yaml").read_text(encoding="utf-8")
    assert '"--beat"' in deployment
    assert "celerybeat-schedule" in deployment
