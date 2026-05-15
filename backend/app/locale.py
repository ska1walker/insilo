"""UI-Locale-Resolution für Insilo (v0.1.43+).

Vier Stufen Resolution-Reihenfolge:
    1. User-Override (`users.ui_locale`)
    2. Org-Default (`org_settings.ui_locale`)
    3. Browser-Header (`Accept-Language`)
    4. Hardcoded Default `'de'`

Reines Python-Modul ohne I/O — Auth-Layer + Router lesen die persistente
Werte aus der DB und kombinieren sie hier.
"""

from __future__ import annotations

import re
from typing import Literal

SUPPORTED: tuple[str, ...] = ("de", "en", "fr", "es", "it")
DEFAULT: str = "de"

Locale = Literal["de", "en", "fr", "es", "it"]
LocaleSource = Literal["user", "org", "browser", "default"]


_ACCEPT_LANG_ITEM = re.compile(r"\s*([a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?)\s*(?:;\s*q=([0-9.]+))?\s*")


def parse_accept_language(header: str | None) -> list[str]:
    """Parse the Accept-Language header into a quality-sorted list of
    primary-language codes (e.g. 'en-US' → 'en'). Returns [] if the
    header is missing or unparseable.
    """
    if not header:
        return []
    items: list[tuple[str, float]] = []
    for part in header.split(","):
        m = _ACCEPT_LANG_ITEM.fullmatch(part)
        if not m:
            continue
        tag = m.group(1).lower()
        try:
            q = float(m.group(2)) if m.group(2) else 1.0
        except ValueError:
            q = 1.0
        # Wildcard '*' wird ignoriert — keine sinnvolle Mapping
        if tag == "*":
            continue
        items.append((tag, q))
    items.sort(key=lambda x: -x[1])
    # Reduziere auf primary language code ('en-US' → 'en'), de-dupe.
    seen: set[str] = set()
    out: list[str] = []
    for tag, _q in items:
        primary = tag.split("-", 1)[0]
        if primary in seen:
            continue
        seen.add(primary)
        out.append(primary)
    return out


def resolve_locale(
    *,
    user_locale: str | None,
    org_locale: str | None,
    accept_language: str | None,
) -> tuple[str, LocaleSource]:
    """Apply the four-stage resolution. Returns (locale, source) where
    source documents WHICH stage matched — useful for the locale-API
    response so the UI can show "Sprache: aktuell vom Browser erkannt".
    """
    if user_locale in SUPPORTED:
        return user_locale, "user"
    if org_locale in SUPPORTED:
        return org_locale, "org"
    for candidate in parse_accept_language(accept_language):
        if candidate in SUPPORTED:
            return candidate, "browser"
    return DEFAULT, "default"


__all__ = [
    "DEFAULT",
    "Locale",
    "LocaleSource",
    "SUPPORTED",
    "parse_accept_language",
    "resolve_locale",
]
