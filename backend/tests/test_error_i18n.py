"""Tests for backend error-message i18n (v0.1.45+).

Covers:
  - `resolve_error_locale`: Accept-Language → DE/EN/DEFAULT
  - `translate`: lookup, formatting, fallback chains
  - `http_error`: pulls locale from contextvar, raises HTTPException
"""

from __future__ import annotations

import pytest

from app.errors import (
    DEFAULT,
    SUPPORTED,
    current_locale,
    http_error,
    reset_request_locale,
    resolve_error_locale,
    set_request_locale,
    translate,
)


# ─── resolve_error_locale ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, "de"),
        ("", "de"),
        ("de", "de"),
        ("en-US,en;q=0.9", "en"),
        ("fr-FR,fr;q=0.9", "de"),  # FR falls back — not supported yet
        ("es,en;q=0.5", "en"),  # es not supported, en is next
        ("it,fr;q=0.8", "de"),  # neither supported → DEFAULT
        ("*", "de"),
        ("xx-YY", "de"),  # unparseable / unknown
    ],
)
def test_resolve_error_locale(header: str | None, expected: str) -> None:
    assert resolve_error_locale(header) == expected


def test_supported_is_de_en_only() -> None:
    """Phase 2 contract: only DE+EN — FR/ES/IT come in v0.1.46."""
    assert set(SUPPORTED) == {"de", "en"}
    assert DEFAULT == "de"


# ─── translate ───────────────────────────────────────────────────────


def test_translate_known_de() -> None:
    assert translate("tags.name_empty", "de") == "Name darf nicht leer sein."


def test_translate_known_en() -> None:
    assert translate("tags.name_empty", "en") == "Name must not be empty."


def test_translate_with_params() -> None:
    out = translate("tags.duplicate", "de", name="Mandant Müller")
    assert "Mandant Müller" in out


def test_translate_unsupported_locale_falls_back_to_en() -> None:
    # fr/es/it aren't in the catalogue yet — return EN
    out = translate("tags.not_found", "fr")
    assert out == "Tag not found."


def test_translate_unknown_key_returns_key() -> None:
    assert translate("does.not.exist", "de") == "does.not.exist"


def test_translate_missing_param_returns_template_unformatted() -> None:
    # Graceful: if caller forgets a param, we don't crash
    out = translate("tags.duplicate", "de")
    assert "{name}" in out


# ─── contextvar + http_error ─────────────────────────────────────────


def test_current_locale_default() -> None:
    # Outside a request, the default value applies.
    assert current_locale() == DEFAULT


def test_set_and_reset_request_locale() -> None:
    token = set_request_locale("en")
    try:
        assert current_locale() == "en"
    finally:
        reset_request_locale(token)
    assert current_locale() == DEFAULT


def test_set_request_locale_rejects_unsupported() -> None:
    token = set_request_locale("xx")
    try:
        # Unsupported codes are coerced to DEFAULT.
        assert current_locale() == DEFAULT
    finally:
        reset_request_locale(token)


def test_http_error_uses_current_locale() -> None:
    token = set_request_locale("en")
    try:
        exc = http_error(404, "meeting.not_found")
        assert exc.status_code == 404
        assert exc.detail == "Meeting not found."
    finally:
        reset_request_locale(token)


def test_http_error_default_locale_is_de() -> None:
    exc = http_error(404, "meeting.not_found")
    assert exc.detail == "Besprechung nicht gefunden."


def test_http_error_with_params() -> None:
    token = set_request_locale("de")
    try:
        exc = http_error(400, "tags.invalid_color", color="'xyz'")
        assert "'xyz'" in str(exc.detail)
        assert "Farbe" in str(exc.detail)
    finally:
        reset_request_locale(token)
