"""Lange Aufnahmen: Zeitriegel, Wächter, erneut verarbeiten.

Anlass (0.1.99): Aufnahmen über etwa zwanzig Minuten wurden angenommen
und gespeichert, aber die Verarbeitung brach ab. Die Ursache war kein
Fehler im Ablauf, sondern ein Missverhältnis — gemessen am 16.9.2026 auf
einer Box ohne GPU braucht `large-v3` (int8, sechs Kerne, beam 5, mit
Sprechertrennung) **795 s für 626 s Audio**, während im Code ein fester
Riegel von 25 Minuten stand und Celery nach 30 Minuten hart abbrach.

Die Tests halten drei Dinge fest:

1. Der Riegel hängt an der Länge der Aufnahme und liegt über dem, was die
   Messung gebraucht hat.
2. Das weiche Zeitlimit liegt **vor** dem harten — daran hängt, ob eine
   Besprechung sauber auf „fehlgeschlagen" landet oder ewig auf „wird
   transkribiert" stehen bleibt.
3. Was das harte Limit trotzdem erwischt, sammelt der Wächter ein, und
   der Nutzer kann die Verarbeitung erneut anstoßen.
"""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import httpx
import pytest
from celery.exceptions import SoftTimeLimitExceeded
from fastapi.testclient import TestClient

from app.tasks import waechter as waechter_modul
from app.verarbeitungszeit import (
    geschaetzte_dauer,
    hartes_limit,
    stt_zeitlimit,
    weiches_limit,
)

# Die Messung vom 16.9.2026, gegen die gerechnet wird.
MESSUNG_AUDIO_SEC = 626
MESSUNG_BYTES = 9_300_000
MESSUNG_GEBRAUCHT_SEC = 795

ORG = UUID("00000000-0000-0000-0000-0000000000aa")
NUTZER = UUID("00000000-0000-0000-0000-0000000000bb")


# ---------------------------------------------------------------------------
# Der Riegel
# ---------------------------------------------------------------------------


def test_der_riegel_liegt_ueber_der_gemessenen_rechenzeit() -> None:
    """Die Regression, um die es geht.

    Hier stand `httpx.Timeout(60 * 25)`. Für diese Datei reichte das noch
    knapp; ab ungefähr zwanzig Minuten Aufnahme nicht mehr.
    """
    riegel = stt_zeitlimit(MESSUNG_AUDIO_SEC, MESSUNG_BYTES)
    assert riegel > MESSUNG_GEBRAUCHT_SEC * 2, (
        f"Riegel {riegel:.0f}s lässt gegenüber den gemessenen "
        f"{MESSUNG_GEBRAUCHT_SEC}s zu wenig Luft"
    )


@pytest.mark.parametrize("minuten", [20, 30, 45, 60, 90])
def test_lange_aufnahmen_bekommen_mehr_zeit_als_sie_brauchen(minuten: int) -> None:
    """Der Faktor aus der Messung, auf längere Aufnahmen gerechnet.

    1,3 s Rechenzeit je Sekunde Audio — und zwar auf dem langsamsten Weg,
    den Insilo mitbringt. Was der Riegel zulässt, muss darüber liegen,
    sonst bricht er eine Verarbeitung ab, die fertig geworden wäre.
    """
    dauer = minuten * 60
    # Grob so viel schreibt MediaRecorder in Opus (15 kB/s).
    bytes_ = dauer * 15_000
    gebraucht = dauer * (MESSUNG_GEBRAUCHT_SEC / MESSUNG_AUDIO_SEC)
    assert stt_zeitlimit(dauer, bytes_) > gebraucht


def test_die_alte_feste_grenze_haette_hier_zugeschlagen() -> None:
    """Zum Vergleich: was vorher passierte, in Zahlen."""
    dreissig_minuten = 30 * 60
    gebraucht = dreissig_minuten * (MESSUNG_GEBRAUCHT_SEC / MESSUNG_AUDIO_SEC)
    assert gebraucht > 60 * 25, "sonst erklärt die Messung den Ausfall nicht"
    assert stt_zeitlimit(dreissig_minuten, dreissig_minuten * 15_000) > gebraucht


def test_kurzes_bekommt_trotzdem_eine_untergrenze() -> None:
    """Ein Schnipsel darf nicht an einem Riegel von zwei Sekunden scheitern."""
    assert stt_zeitlimit(3, 40_000) >= 600


def test_der_riegel_ist_nach_oben_gedeckelt() -> None:
    """Ein hängender Dienst darf den einen Worker nicht für immer belegen."""
    assert stt_zeitlimit(24 * 3600, 2_000_000_000) == float(hartes_limit())


def test_dauer_aus_der_datei_wenn_der_browser_nichts_weiss() -> None:
    """Eine hochgeladene Datei ohne lesbare Metadaten steht auf 1 Sekunde.

    Ginge der Riegel davon aus, bekäme ausgerechnet die eingespielte
    Zwei-Stunden-Aufnahme die kürzeste Zeit.
    """
    assert geschaetzte_dauer(1, 60_000_000) > 3600
    assert stt_zeitlimit(1, 60_000_000) > 3600


def test_die_groessere_der_beiden_schaetzungen_gewinnt() -> None:
    """Eine gute Dauer darf eine schlechte Größenschätzung nicht verlieren."""
    # Sehr stark komprimiert: wenige Bytes, aber wirklich eine Stunde lang.
    assert geschaetzte_dauer(3600, 1_000_000) == 3600.0


# ---------------------------------------------------------------------------
# Weiches vor hartem Limit
# ---------------------------------------------------------------------------


def test_weiches_limit_kommt_vor_dem_harten() -> None:
    """Daran hängt, ob eine gescheiterte Besprechung sichtbar scheitert.

    Beim weichen Limit fliegt eine Ausnahme *in* der Aufgabe, die gefangen
    wird und den Zustand setzt. Das harte Limit killt den Prozess — dann
    läuft kein `except` mehr.
    """
    assert weiches_limit() < hartes_limit()
    assert hartes_limit() - weiches_limit() >= 120


def test_erkennung_und_zusammenfassung_bringen_eigene_limits_mit() -> None:
    """Die globalen aus `app.worker` sind für Webhooks bemessen, nicht für Audio."""
    from app.tasks.summarize import summarize_meeting
    from app.tasks.transcribe import transcribe_meeting

    for aufgabe in (transcribe_meeting, summarize_meeting):
        assert aufgabe.time_limit == hartes_limit(), aufgabe.name
        assert aufgabe.soft_time_limit == weiches_limit(), aufgabe.name


def test_keine_festen_riegel_mehr_im_erkennungspfad() -> None:
    """Der Rückfall, vor dem der ganze Abschnitt schützt."""
    from app.tasks import transcribe

    quelle = inspect.getsource(transcribe)
    assert "Timeout(60 * 25)" not in quelle
    assert "Timeout(60 * 10)" not in quelle
    assert quelle.count("httpx.Timeout(zeitlimit)") == 3


# ---------------------------------------------------------------------------
# Der Fehlertext
# ---------------------------------------------------------------------------


def test_zeitlimit_wird_zu_einem_satz_mit_einem_ausweg() -> None:
    """`SoftTimeLimitExceeded(14100,)` sagt niemandem, was zu tun ist."""
    from app.tasks.transcribe import _fehlertext

    text = _fehlertext(SoftTimeLimitExceeded(14100))
    assert "Einstellungen" in text
    assert "Aufnahme" in text
    assert "SoftTimeLimit" not in text


def test_auch_der_httpx_riegel_bekommt_den_satz() -> None:
    from app.tasks.transcribe import _fehlertext

    assert "Einstellungen" in _fehlertext(httpx.ReadTimeout("zu lang"))


def test_andere_fehler_kommen_unveraendert_durch() -> None:
    """Die Meldungen in `transcribe.py` sind für den Nutzer geschrieben."""
    from app.tasks.transcribe import _fehlertext

    assert _fehlertext(RuntimeError("Für die Spracherkennung fehlt die Modell-ID.")) == (
        "Für die Spracherkennung fehlt die Modell-ID."
    )


# ---------------------------------------------------------------------------
# Der Wächter
# ---------------------------------------------------------------------------


class _Verbindung:
    def __init__(self, zeilen: list[dict] | None = None) -> None:
        self.zeilen = zeilen or []
        self.abfragen: list[tuple] = []

    async def fetch(self, sql: str, *args):
        self.abfragen.append((sql, args))
        return self.zeilen

    async def close(self) -> None:
        return None


@pytest.fixture
def wacht(monkeypatch: pytest.MonkeyPatch):
    verbindung = _Verbindung()
    gesendet: list[tuple] = []

    async def _connect():
        return verbindung

    monkeypatch.setattr(waechter_modul, "_connect", _connect)

    class _App:
        @staticmethod
        def send_task(name, args=None, **_kw):
            gesendet.append((name, tuple(args or ())))

    import app.worker as worker_modul

    monkeypatch.setattr(worker_modul, "celery_app", _App)
    return verbindung, gesendet


def test_waechter_sammelt_nur_schwebende_zustaende_ein(wacht) -> None:
    verbindung, _ = wacht
    waechter_modul.waechter()

    sql, args = verbindung.abfragen[0]
    assert "set status = 'failed'" in sql
    assert "deleted_at is null" in sql
    zustaende = args[2]
    assert set(zustaende) == {"queued", "transcribing", "summarizing", "embedding"}
    # Was dem Browser gehört, gehört nicht dem Wächter.
    assert "draft" not in zustaende
    assert "uploading" not in zustaende
    # Und was fertig ist, wird nicht angefasst.
    assert "ready" not in zustaende
    assert "transcribed" not in zustaende


def test_waechter_wartet_laenger_als_das_harte_limit(wacht) -> None:
    """Sonst erklärt er eine Aufgabe für tot, die noch arbeitet."""
    verbindung, _ = wacht
    waechter_modul.waechter()

    _sql, args = verbindung.abfragen[0]
    grenze = args[0]
    assert grenze > hartes_limit()
    assert grenze >= hartes_limit() + 10 * 60


def test_waechter_ueberschreibt_keine_vorhandene_fehlermeldung(wacht) -> None:
    """Ein echter Grund ist genauer als unsere allgemeine Vermutung."""
    verbindung, _ = wacht
    waechter_modul.waechter()

    sql, _args = verbindung.abfragen[0]
    assert "coalesce(nullif(error_message, ''), $2)" in sql


def test_waechter_meldet_jede_eingesammelte_besprechung(wacht) -> None:
    verbindung, gesendet = wacht
    eine, zwei = uuid4(), uuid4()
    verbindung.zeilen = [
        {"id": eine, "status": "transcribing", "updated_at": None},
        {"id": zwei, "status": "summarizing", "updated_at": None},
    ]

    ergebnis = waechter_modul.waechter()

    assert ergebnis["eingesammelt"] == 2
    assert gesendet == [
        ("notify_webhook", (str(eine), "meeting.failed")),
        ("notify_webhook", (str(zwei), "meeting.failed")),
    ]


def test_waechter_schweigt_wenn_nichts_haengt(wacht) -> None:
    _verbindung, gesendet = wacht
    assert waechter_modul.waechter()["eingesammelt"] == 0
    assert gesendet == []


def test_waechter_stoesst_nichts_von_selbst_neu_an() -> None:
    """Ein zweiter Lauf, der wieder ins Limit rennt, hilft niemandem.

    Er belegt den einen Worker für Stunden und endet genauso. Der Nutzer
    entscheidet, ob es einen zweiten Versuch gibt.
    """
    quelle = inspect.getsource(waechter_modul)
    assert "transcribe_meeting" not in quelle
    assert "summarize_meeting" not in quelle


def test_waechter_laeuft_regelmaessig() -> None:
    """Täglich reicht nicht — eine hängende Besprechung blockiert den Nutzer."""
    from app.worker import celery_app

    eintrag = celery_app.conf.beat_schedule["waechter"]
    assert eintrag["task"] == "waechter"
    assert eintrag["schedule"] <= 600


# ---------------------------------------------------------------------------
# Erneut verarbeiten
# ---------------------------------------------------------------------------


class _EndpunktVerbindung:
    def __init__(self, zeile: dict | None) -> None:
        self.zeile = zeile
        self.ausgefuehrt: list[tuple] = []

    async def fetchrow(self, _sql: str, *_args):
        return self.zeile

    async def execute(self, sql: str, *args):
        self.ausgefuehrt.append((sql, args))


@pytest.fixture
def klient(monkeypatch: pytest.MonkeyPatch):
    from app import main
    from app.auth import CurrentUser, get_current_user
    from app.config import settings
    from app.routers import meetings

    zustand: dict = {"zeile": None, "eingereiht": [], "delay_scheitert": False}

    def _delay(mid):
        if zustand["delay_scheitert"]:
            raise RuntimeError("Warteschlange weg")
        zustand["eingereiht"].append(mid)

    monkeypatch.setattr(settings, "internal_token", "")
    monkeypatch.setattr(
        meetings, "transcribe_meeting", type("T", (), {"delay": staticmethod(_delay)})
    )

    @asynccontextmanager
    async def _acquire_as(_user_id):
        verbindung = _EndpunktVerbindung(zustand["zeile"])
        zustand["verbindung"] = verbindung
        yield verbindung

    monkeypatch.setattr(meetings, "acquire_as", _acquire_as)

    async def _nutzer() -> CurrentUser:
        return CurrentUser(user_id=NUTZER, org_id=ORG, olares_username="kai")

    main.app.dependency_overrides[get_current_user] = _nutzer
    yield TestClient(main.app, raise_server_exceptions=False), zustand
    main.app.dependency_overrides.clear()


def _anstossen(k: TestClient, mid: UUID | None = None):
    return k.post(f"/api/v1/meetings/{mid or uuid4()}/retry-transcription")


def test_erneut_verarbeiten_reiht_wieder_ein(klient) -> None:
    k, zustand = klient
    mid = uuid4()
    zustand["zeile"] = {"id": mid, "status": "failed", "audio_path": "org/a.webm"}

    antwort = _anstossen(k, mid)

    assert antwort.status_code == 202, antwort.text
    assert zustand["eingereiht"] == [str(mid)]
    sql, _args = zustand["verbindung"].ausgefuehrt[0]
    assert "status = 'queued'" in sql
    # Die alte Meldung muss weg, sonst steht sie neben dem neuen Lauf.
    assert "error_message = null" in sql


def test_ohne_aufnahme_geht_es_nicht(klient) -> None:
    """Die Aufbewahrungsfrist holt irgendwann den Ton, nicht das Transkript."""
    k, zustand = klient
    zustand["zeile"] = {"id": uuid4(), "status": "ready", "audio_path": None}

    antwort = _anstossen(k)

    assert antwort.status_code == 409
    assert zustand["eingereiht"] == []
    assert "keine Aufnahme" in antwort.json()["detail"]


@pytest.mark.parametrize("status", ["transcribing", "summarizing", "embedding"])
def test_kein_zweiter_lauf_neben_dem_ersten(klient, status: str) -> None:
    """Zwei Schreiber auf demselben Transkript wären ein Datenschaden."""
    k, zustand = klient
    zustand["zeile"] = {"id": uuid4(), "status": status, "audio_path": "org/a.webm"}

    antwort = _anstossen(k)

    assert antwort.status_code == 409
    assert zustand["eingereiht"] == []


def test_unbekannte_besprechung_ist_vierhundertvier(klient) -> None:
    k, zustand = klient
    zustand["zeile"] = None

    assert _anstossen(k).status_code == 404


def test_warteschlange_weg_laesst_die_besprechung_nicht_in_der_luft(klient) -> None:
    """Sonst stünde sie auf „in Warteschlange", bis der Wächter kommt."""
    k, zustand = klient
    zustand["zeile"] = {"id": uuid4(), "status": "failed", "audio_path": "org/a.webm"}
    zustand["delay_scheitert"] = True

    antwort = _anstossen(k)

    assert antwort.status_code == 503
    sql, _args = zustand["verbindung"].ausgefuehrt[-1]
    assert "status = 'failed'" in sql
