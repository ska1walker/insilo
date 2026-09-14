"""Die Bereitschaftsprobe darf das Zugriffsprotokoll nicht fluten.

Anlass: am 14.9.2026 reichte das Backend-Protokoll nur 16 Minuten zurück,
weil Kubernetes `/health` alle fünf Sekunden abfragt.
"""

from __future__ import annotations

import logging

from app.main import OhneBereitschaftsprobe


def _zeile(methode: str, pfad: str, status: int) -> logging.LogRecord:
    # Genau die Form, in der uvicorn (h11_impl/httptools_impl) protokolliert.
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 0,
        '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.7:51234", methode, pfad, "1.1", status),
        None,
    )


def test_erfolgreiche_probe_faellt_weg() -> None:
    assert OhneBereitschaftsprobe().filter(_zeile("GET", "/health", 200)) is False


def test_fehler_auf_health_bleibt_sichtbar() -> None:
    assert OhneBereitschaftsprobe().filter(_zeile("GET", "/health", 503)) is True


def test_alles_andere_bleibt() -> None:
    f = OhneBereitschaftsprobe()
    assert f.filter(_zeile("POST", "/api/v1/recordings", 400)) is True
    assert f.filter(_zeile("GET", "/health/db", 200)) is True
    assert f.filter(_zeile("GET", "/api/v1/meetings", 200)) is True


def test_haengt_am_logger_von_uvicorn() -> None:
    assert any(
        isinstance(f, OhneBereitschaftsprobe)
        for f in logging.getLogger("uvicorn.access").filters
    )


def test_fremde_zeilen_ohne_argumente_laufen_durch() -> None:
    zeile = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 0, "hallo", None, None)
    assert OhneBereitschaftsprobe().filter(zeile) is True
