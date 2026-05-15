"""Tests for the four-stage UI-locale resolution.

Resolution order (top to bottom = highest priority first):
  1. User-Override
  2. Org-Default
  3. Browser Accept-Language
  4. Hardcoded 'de'
"""

from __future__ import annotations

import pytest

from app.locale import (
    DEFAULT,
    SUPPORTED,
    parse_accept_language,
    resolve_locale,
)

# ─── parse_accept_language ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, []),
        ("", []),
        ("de", ["de"]),
        ("en-US,en;q=0.9", ["en"]),
        ("fr-FR,fr;q=0.9,en;q=0.5,de;q=0.3", ["fr", "en", "de"]),
        # Quality-Sort: en kommt vor de obwohl es später steht
        ("de;q=0.5,en;q=0.9", ["en", "de"]),
        # Wildcard wird ignoriert
        ("*", []),
        ("de,*", ["de"]),
        # Malformed: einige Items werden geskipt, der Rest kommt durch
        ("de;malformed,en", ["en"]),
        # Whitespace-Tolerance
        ("  de , en ; q=0.5 ", ["de", "en"]),
        # Region-Codes werden auf primary language gemapped (en-GB → en)
        ("en-GB,en-US;q=0.8", ["en"]),
    ],
)
def test_parse_accept_language(header, expected):
    assert parse_accept_language(header) == expected


# ─── resolve_locale ─────────────────────────────────────────────────────


def test_resolve_user_override_wins():
    """User-Setting hat höchste Priorität — schlägt Org + Browser."""
    locale, source = resolve_locale(
        user_locale="fr",
        org_locale="de",
        accept_language="en",
    )
    assert locale == "fr"
    assert source == "user"


def test_resolve_org_default_when_no_user():
    """Ohne User-Override: Org-Default."""
    locale, source = resolve_locale(
        user_locale=None,
        org_locale="es",
        accept_language="en",
    )
    assert locale == "es"
    assert source == "org"


def test_resolve_browser_when_no_user_no_org():
    """Ohne User + Org: Browser-Accept-Language."""
    locale, source = resolve_locale(
        user_locale=None,
        org_locale=None,
        accept_language="it-IT,it;q=0.9,en;q=0.5",
    )
    assert locale == "it"
    assert source == "browser"


def test_resolve_falls_back_to_default():
    """Wenn nichts passt: hardcoded 'de'."""
    locale, source = resolve_locale(
        user_locale=None,
        org_locale=None,
        accept_language=None,
    )
    assert locale == DEFAULT
    assert source == "default"


def test_resolve_unsupported_user_locale_is_ignored():
    """Ein User mit gespeicherter 'ja'-Locale wird auf die nächste Stufe
    durchgereicht (data integrity defensiv)."""
    locale, source = resolve_locale(
        user_locale="ja",
        org_locale="fr",
        accept_language=None,
    )
    assert locale == "fr"
    assert source == "org"


def test_resolve_unsupported_browser_locale_skipped():
    """Wenn die Browser-Sprache (z. B. ja) nicht unterstützt wird,
    fallen wir auf default 'de' — nicht auf 'ja'."""
    locale, source = resolve_locale(
        user_locale=None,
        org_locale=None,
        accept_language="ja-JP",
    )
    assert locale == DEFAULT
    assert source == "default"


def test_resolve_browser_picks_first_supported():
    """Browser bevorzugt zh, dann ja, dann fr — wir nehmen das erste
    unterstützte (fr) und ignorieren die nicht unterstützten."""
    locale, source = resolve_locale(
        user_locale=None,
        org_locale=None,
        accept_language="zh-CN,ja;q=0.9,fr;q=0.5",
    )
    assert locale == "fr"
    assert source == "browser"


@pytest.mark.parametrize("supported", SUPPORTED)
def test_all_supported_locales_resolve_as_user_setting(supported):
    """Jede unterstützte Locale ist als User-Override gültig."""
    locale, source = resolve_locale(
        user_locale=supported,
        org_locale=None,
        accept_language=None,
    )
    assert locale == supported
    assert source == "user"


def test_empty_string_user_locale_is_treated_as_no_override():
    """Leerer String darf nicht als gültige Locale durchgehen — er
    bedeutet 'kein Override' und sollte zur nächsten Stufe weiterleiten."""
    locale, source = resolve_locale(
        user_locale="",
        org_locale="en",
        accept_language=None,
    )
    assert locale == "en"
    assert source == "org"
