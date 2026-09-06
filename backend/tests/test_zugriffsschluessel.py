"""Prüft das Hashen der Zugriffsschlüssel — ohne passlib.

Der Anlass war ein Ausfall in Produktion, kein Verdacht: `pyproject.toml`
führte `passlib[bcrypt]>=1.7.4` ohne Obergrenze. passlib 1.7.4 ist von
2020 und mit bcrypt ab 4.1 unverträglich — beim Erkennen des Backends
übergibt es einen überlangen Wert, den neuere bcrypt-Fassungen ablehnen
statt ihn zu kürzen.

Am 5.9.2026 im Backend-Pod nachgemessen (bcrypt 5.0.0):

    AttributeError: module 'bcrypt' has no attribute '__about__'
    ValueError: password cannot be longer than 72 bytes

Damit war die **gesamte externe Schnittstelle tot**: kein Schlüssel ließ
sich anlegen und keiner prüfen. Aufgefallen ist es nicht durch einen
Test, sondern beim Anlegen eines Schlüssels über die laufende App.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.auth_api import (
    KEY_PREFIX,
    KEY_PREFIX_LEN,
    MAX_TOKEN_BYTES,
    _hashen,
    _pruefen,
    generate_api_key,
)

WURZEL = Path(__file__).resolve().parents[2]


def test_schluessel_entsteht_und_prueft() -> None:
    """Der Weg, der auf der Box nicht mehr ging."""
    voll, praefix, hash_ = generate_api_key()
    assert voll.startswith(KEY_PREFIX)
    assert praefix == voll[:KEY_PREFIX_LEN]
    assert _pruefen(voll, hash_) is True


def test_falscher_schluessel_passt_nicht() -> None:
    voll, _, hash_ = generate_api_key()
    assert _pruefen(voll + "x", hash_) is False
    assert _pruefen(KEY_PREFIX + "ausgedacht", hash_) is False


def test_bestehende_hashes_pruefen_weiter() -> None:
    """Die Schlüssel auf der Box wurden von passlib geschrieben.

    passlib hat kein eigenes Format erfunden, sondern bcrypt benutzt —
    `checkpw` liest sie deshalb weiter. Wäre das nicht so, hätte der
    Umstieg jeden ausgestellten Schlüssel entwertet.

    Der Hash unten ist ein echter bcrypt-Hash im Format `$2b$`, wie
    passlib ihn erzeugt hat.
    """
    # bcrypt-Hash von "inskey_probe", Kostenfaktor 12
    alt = "$2b$12$77sRbKsuBJnE3JgHdbv6t./8gNM/4Li.eTy9JLzA9b9s96dFC4v6."
    assert _pruefen("inskey_probe", alt) is True
    assert _pruefen("inskey_falsch", alt) is False


def test_unbrauchbarer_hash_ist_kein_treffer_sondern_ein_nein() -> None:
    """Eine Ausnahme hier würde mit 500 antworten.

    Und ein 500 statt eines 401 verrät, dass zum Präfix überhaupt eine
    Zeile existiert — der Unterschied zwischen „Schlüssel unbekannt" und
    „Schlüssel bekannt, aber kaputt gespeichert".
    """
    for kaputt in ("", "kein-hash", "$2b$12$zu-kurz", "x" * 200):
        assert _pruefen("inskey_egal", kaputt) is False


def test_zu_langer_schluessel_wird_nicht_stillschweigend_gekuerzt() -> None:
    """bcrypt schneidet nach 72 Byte ab — das darf nicht unbemerkt passieren.

    Sonst wären zwei Schlüssel, die sich erst ab Byte 73 unterscheiden,
    derselbe. Unsere sind rund 39 Zeichen lang; die Grenze steht für den
    Fall, dass jemand das Format ändert.
    """
    zu_lang = KEY_PREFIX + "z" * MAX_TOKEN_BYTES
    try:
        _hashen(zu_lang)
    except ValueError as exc:
        assert "72" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("zu langer Schlüssel wurde klaglos gehasht")


def test_unsere_schluessel_bleiben_unter_der_grenze() -> None:
    voll, _, _ = generate_api_key()
    assert len(voll.encode("utf-8")) < MAX_TOKEN_BYTES


def test_passlib_ist_raus() -> None:
    """Ohne diesen Test kommt die Abhängigkeit beim nächsten Aufräumen zurück.

    Die Bibliothek ist seit 2020 unverändert; ihr Backend-Erkenner ist
    der Grund für den Ausfall gewesen.
    """
    # Nur echte Abhängigkeitszeilen zählen — im Kommentar daneben steht,
    # warum passlib weg ist, und das soll stehen bleiben.
    pyproject = (WURZEL / "backend/pyproject.toml").read_text(encoding="utf-8")
    eintraege = re.findall(r'^\s*"([^"]+)",\s*$', pyproject, re.M)
    assert not [e for e in eintraege if e.startswith("passlib")], (
        "passlib steht wieder in den Abhängigkeiten"
    )
    assert "bcrypt>=4.1" in eintraege, "bcrypt fehlt oder ist anders gepinnt"

    # Im Text darf passlib vorkommen — dort steht, warum es weg ist.
    # Geprüft wird die Verwendung.
    quelle = (WURZEL / "backend/app/auth_api.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+passlib", quelle, re.M)
    assert "CryptContext" not in quelle
    assert re.search(r"^import bcrypt$", quelle, re.M)
