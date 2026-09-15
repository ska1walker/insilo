"""Tonaufnahmen annehmen: Formate, Größe, Reihenfolge, gemessene Dauer.

Anlass (0.1.97): mit dem Hochladen von Dateien kommen Formate, die aus dem
Browser-Recorder nie kamen. Eine mp3 landete als `.webm` und wurde als
`application/octet-stream` ausgeliefert; `max_upload_mb` stand in der
Konfiguration und wurde nirgends geprüft; eine abgelehnte Vorlage ließ die
schon geschriebene Datei verwaist zurück.
"""

from __future__ import annotations

import io
from contextlib import asynccontextmanager
from datetime import UTC
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.audioformat import MEDIENTYP, audio_endung
from app.tasks.transcribe import _dateiname, _dauer_sekunden

# ---------------------------------------------------------------------------
# Formate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mime", "dateiname", "endung"),
    [
        ("audio/webm;codecs=opus", None, "webm"),
        ("audio/mp4;codecs=mp4a.40.2", None, "m4a"),
        ("audio/x-m4a", None, "m4a"),  # so meldet das iPhone .m4a
        ("video/mp4", None, "m4a"),
        ("audio/mpeg", None, "mp3"),
        ("audio/mp3", None, "mp3"),
        ("audio/aac", None, "aac"),
        ("audio/aacp", None, "aac"),
        ("audio/ogg;codecs=opus", None, "ogg"),
        ("audio/opus", None, "ogg"),
        ("audio/wav", None, "wav"),
        ("audio/x-wav", None, "wav"),
        ("audio/vnd.wave", None, "wav"),
        ("audio/flac", None, "flac"),
        ("audio/x-flac", None, "flac"),
        ("audio/3gpp", None, "3gp"),
        # Kein oder nichtssagender Typ: die Endung entscheidet.
        ("", "Besprechung.MP3", "mp3"),
        ("application/octet-stream", "notiz.m4a", "m4a"),
        ("", "ohne-endung", "webm"),
        ("", "skript.exe", "webm"),
    ],
)
def test_audio_endung(mime: str, dateiname: str | None, endung: str) -> None:
    assert audio_endung(mime, dateiname) == endung


def test_jede_endung_hat_einen_medientyp() -> None:
    """Sonst liefert `routers/audio.py` sie als octet-stream aus."""
    fuer_alle = {audio_endung(m) for m in (
        "audio/webm", "audio/mp4", "audio/aac", "audio/ogg", "audio/wav",
        "audio/mpeg", "audio/flac", "audio/3gpp",
    )}
    assert fuer_alle <= set(MEDIENTYP)


def test_auslieferung_und_stt_benutzen_dieselbe_liste() -> None:
    from app.routers import audio

    assert audio._AUDIO_MIME is MEDIENTYP
    assert _dateiname("audio/x-m4a") == "recording.m4a"
    assert _dateiname("audio/mpeg") == "recording.mp3"


# ---------------------------------------------------------------------------
# Dauer aus der Spracherkennung
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dauer", "sekunden"),
    [(5400.4, 5400), (0.3, 1), (None, None), (0.0, None), (-2.0, None), (float("inf"), None), (float("nan"), None)],
)
def test_dauer_sekunden(dauer: float | None, sekunden: int | None) -> None:
    assert _dauer_sekunden(dauer) == sekunden


def test_ohne_dauer_zaehlt_das_ende_des_letzten_segments() -> None:
    """Ein fremder STT-Dienst lässt `duration` im verbose_json auch mal weg."""
    segmente = [{"start": 0.0, "end": 12.5}, {"start": 12.5, "end": 5399.6}]
    assert _dauer_sekunden(None, segmente) == 5400
    assert _dauer_sekunden(0.0, []) is None
    assert _dauer_sekunden(61.0, segmente) == 61  # eine gemessene Dauer gewinnt


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------


def test_upload_file_schreibt_stueckweise_dieselben_bytes(tmp_path, monkeypatch) -> None:
    from app import storage
    from app.config import settings

    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path))
    inhalt = bytes(range(256)) * 20_000  # ~5 MB, mehrere Stücke
    storage._LocalBackend().upload_file("org/m.mp3", io.BytesIO(inhalt), "audio/mpeg")
    assert (tmp_path / "org" / "m.mp3").read_bytes() == inhalt


# ---------------------------------------------------------------------------
# Der Endpunkt: erst prüfen, dann schreiben
# ---------------------------------------------------------------------------

ORG = UUID("a0000000-0000-4000-8000-000000000001")
NUTZER = UUID("b0000000-0000-4000-8000-000000000001")


class _Verbindung:
    def __init__(self, *, vorlage_sichtbar: bool = True, insert_scheitert: bool = False) -> None:
        self.vorlage_sichtbar = vorlage_sichtbar
        self.insert_scheitert = insert_scheitert
        self.eingefuegt: tuple | None = None

    async def fetchval(self, sql: str, *args):
        return 1 if self.vorlage_sichtbar else None

    async def fetchrow(self, sql: str, *args):
        if self.insert_scheitert:
            raise RuntimeError("datenbank weg")
        self.eingefuegt = args
        meeting_id, _org, _user, titel, dauer, key, groesse, _sprache, vorlage, metadaten = args
        import json
        from datetime import datetime

        return {
            "id": meeting_id, "title": titel, "recorded_at": datetime.now(UTC),
            "duration_sec": dauer, "audio_size_bytes": groesse, "audio_path": key,
            "status": "queued", "template_id": vorlage,
            "audio_mime": json.loads(metadaten)["mime_type"],
        }


@pytest.fixture
def aufbau(monkeypatch: pytest.MonkeyPatch):
    from app import main
    from app.auth import CurrentUser, get_current_user
    from app.config import settings
    from app.routers import meetings

    geschrieben: list[str] = []
    inhalte: dict[str, bytes] = {}
    geloescht: list[str] = []
    verbindung = _Verbindung()

    def _schreiben(key, datei, typ):
        # Wirklich lesen: stünde die Datei nach der Größenprüfung am Ende,
        # käme hier eine leere Datei an — genau der stille Verlust.
        geschrieben.append(key)
        inhalte[key] = datei.read()

    monkeypatch.setattr(settings, "internal_token", "")
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    monkeypatch.setattr(meetings, "upload_file", _schreiben)
    monkeypatch.setattr(meetings, "delete_object", lambda key: geloescht.append(key))
    monkeypatch.setattr(meetings, "transcribe_meeting", type("T", (), {"delay": staticmethod(lambda *a, **k: None)}))
    monkeypatch.setattr(meetings, "enqueue_webhook", lambda *a, **k: None)
    monkeypatch.setattr(meetings, "get_presigned_url", lambda key: f"/api/v1/audio/{key}")

    @asynccontextmanager
    async def _acquire_as(_user_id):
        yield verbindung

    monkeypatch.setattr(meetings, "acquire_as", _acquire_as)

    async def _nutzer() -> CurrentUser:
        return CurrentUser(user_id=NUTZER, org_id=ORG, olares_username="kai")

    main.app.dependency_overrides[get_current_user] = _nutzer
    klient = TestClient(main.app, raise_server_exceptions=False)
    klient.inhalte = inhalte  # type: ignore[attr-defined]
    yield klient, geschrieben, geloescht, verbindung
    main.app.dependency_overrides.clear()


def _senden(klient: TestClient, groesse: int, inhalt: bytes | None = None, **felder: str):
    daten = {"title": "Probe", "duration_ms": "0", "mime_type": "audio/mpeg", **felder}
    return klient.post(
        "/api/v1/recordings",
        files={"audio": ("besprechung.mp3", inhalt if inhalt is not None else b"\0" * groesse, "audio/mpeg")},
        data=daten,
    )


def test_angenommen_schreibt_genau_die_gesendeten_bytes(aufbau) -> None:
    klient, geschrieben, geloescht, verbindung = aufbau
    inhalt = bytes(range(256)) * 3000  # ~770 kB, über der Speichergrenze des Spools
    antwort = _senden(klient, 0, inhalt=inhalt)
    assert antwort.status_code == 201, antwort.text
    assert len(geschrieben) == 1 and geschrieben[0].endswith(".mp3")
    assert klient.inhalte[geschrieben[0]] == inhalt
    assert geloescht == []
    assert verbindung.eingefuegt is not None
    assert verbindung.eingefuegt[6] == len(inhalt)  # audio_size_bytes


def test_ohne_verwertbaren_typ_zaehlen_endung_und_passender_medientyp(aufbau) -> None:
    klient, geschrieben, _, verbindung = aufbau
    antwort = klient.post(
        "/api/v1/recordings",
        files={"audio": ("Jour fixe.m4a", b"\1" * 100, "application/octet-stream")},
        data={"title": "Probe", "duration_ms": "0", "mime_type": "application/octet-stream"},
    )
    assert antwort.status_code == 201, antwort.text
    assert geschrieben[0].endswith(".m4a")
    assert antwort.json()["mime_type"] == "audio/mp4"


def test_zu_gross_ergibt_413_und_schreibt_nichts(aufbau) -> None:
    klient, geschrieben, _, _ = aufbau
    antwort = _senden(klient, 1024 * 1024 + 1)
    assert antwort.status_code == 413
    assert "1 MB" in antwort.json()["detail"]
    assert geschrieben == []


def test_kaputte_vorlage_ergibt_400_statt_500_und_schreibt_nichts(aufbau) -> None:
    klient, geschrieben, _, _ = aufbau
    antwort = _senden(klient, 10, template_id="keine-uuid")
    assert antwort.status_code == 400
    assert geschrieben == []


def test_unsichtbare_vorlage_schreibt_nichts(aufbau) -> None:
    klient, geschrieben, _, verbindung = aufbau
    verbindung.vorlage_sichtbar = False
    antwort = _senden(klient, 10, template_id=str(uuid4()))
    assert antwort.status_code == 400
    assert geschrieben == []


def test_scheitert_der_insert_wird_die_datei_wieder_geloescht(aufbau) -> None:
    klient, geschrieben, geloescht, verbindung = aufbau
    verbindung.insert_scheitert = True
    antwort = _senden(klient, 10)
    assert antwort.status_code == 500
    assert len(geschrieben) == 1 and geschrieben[0].endswith(".mp3")
    assert geloescht == geschrieben
