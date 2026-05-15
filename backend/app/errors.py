"""Localized error messages for the public API (v0.1.45+).

Resolves the user's preferred language from the `Accept-Language` header
and returns user-facing strings in DE/EN. Frontend surfaces the
HTTPException `detail` field directly, so this is what lands in the
end-user toast.

Phase 2 scope: DE + EN. FR/ES/IT fall back to EN — they'll be added in
v0.1.46 together with the LLM-prompt localization, when we have a full
translation pass for the long-form copy.

Usage at the call site:

    from app.errors import http_error
    ...
    if not found:
        raise http_error(404, "meeting.not_found")
    if name in existing:
        raise http_error(409, "tags.duplicate", name=name)

The active locale comes from a contextvar set by `locale_middleware`
(wired in `app.main`) once per request. Routes and helpers don't need
to thread the locale through their signatures.
"""

from __future__ import annotations

from contextvars import ContextVar

from fastapi import HTTPException, Request

from app.locale import parse_accept_language

SUPPORTED: tuple[str, ...] = ("de", "en")
DEFAULT: str = "de"

# Two-language catalogue. FR/ES/IT fall through to EN in v0.1.45 —
# v0.1.46 will add them along with the LLM-prompt translations.
ERRORS: dict[str, dict[str, str]] = {
    # ── tags ────────────────────────────────────────────────────────
    "tags.invalid_color": {
        "de": "Ungültige Farbe: {color} (erwartet wird #RRGGBB).",
        "en": "Invalid colour: {color} (expected #RRGGBB).",
    },
    "tags.name_empty": {
        "de": "Name darf nicht leer sein.",
        "en": "Name must not be empty.",
    },
    "tags.duplicate": {
        "de": "Tag „{name}\" existiert bereits.",
        "en": "Tag '{name}' already exists.",
    },
    "tags.not_found": {
        "de": "Tag nicht gefunden.",
        "en": "Tag not found.",
    },
    # ── meetings ───────────────────────────────────────────────────
    "meeting.not_found": {
        "de": "Besprechung nicht gefunden.",
        "en": "Meeting not found.",
    },
    "meeting.no_transcript": {
        "de": "Noch kein Transkript verfügbar.",
        "en": "No transcript available yet.",
    },
    "meeting.no_fields": {
        "de": "Keine Felder zum Aktualisieren angegeben.",
        "en": "No fields to update.",
    },
    "meeting.invalid_speaker_id": {
        "de": "Ungültige Sprecher-ID: {sid}",
        "en": "Invalid speaker id: {sid}",
    },
    "meeting.duplicate_speaker_id": {
        "de": "Doppelte Sprecher-ID: {sid}",
        "en": "Duplicate speaker id: {sid}",
    },
    "meeting.unknown_speaker_ref": {
        "de": "Segment {idx} verweist auf unbekannten Sprecher {sid}.",
        "en": "Segment {idx} references unknown speaker {sid}.",
    },
    # ── templates ──────────────────────────────────────────────────
    "template.not_found": {
        "de": "Vorlage nicht gefunden.",
        "en": "Template not found.",
    },
    "template.not_available": {
        "de": "Vorlage ist nicht verfügbar.",
        "en": "Template not available.",
    },
    "template.system_locked": {
        "de": "System-Vorlagen können nicht gelöscht werden.",
        "en": "System templates cannot be deleted.",
    },
    # ── auth / api keys ───────────────────────────────────────────
    "auth.invalid_key": {
        "de": "Ungültiger API-Schlüssel.",
        "en": "Invalid API key.",
    },
    "auth.missing_scope": {
        "de": "Fehlender Scope: {scope}",
        "en": "Missing scope: {scope}",
    },
    # ── upstream services ─────────────────────────────────────────
    "service.embeddings_unreachable": {
        "de": "Embedding-Service nicht erreichbar.",
        "en": "Embeddings service unreachable.",
    },
    "service.llm_unreachable": {
        "de": "Sprachmodell nicht erreichbar.",
        "en": "LLM unreachable.",
    },
}


_locale_var: ContextVar[str] = ContextVar("insilo_error_locale", default=DEFAULT)


def resolve_error_locale(accept_language: str | None) -> str:
    """Pick the best supported error-message locale from Accept-Language.

    Falls back to `DEFAULT` (de) when nothing matches. Reuses the
    quality-sorting parser from `app.locale` so behaviour stays in sync
    with the UI locale resolution.
    """
    for code in parse_accept_language(accept_language):
        if code in SUPPORTED:
            return code
    return DEFAULT


def translate(key: str, locale: str, **params: object) -> str:
    """Look up `key` for `locale`, format with `params`, return the string.

    Graceful fallback: unknown key returns the key itself; missing
    locale falls back to EN; format errors return the unformatted
    template. Never raises — callers should be able to use this
    unconditionally inside error paths.
    """
    entry = ERRORS.get(key)
    if entry is None:
        return key
    template = entry.get(locale) or entry.get("en") or key
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def current_locale() -> str:
    """Return the locale set for the current request (or DEFAULT)."""
    return _locale_var.get()


def set_request_locale(locale: str) -> object:
    """Stash the locale in the contextvar; returns a token for `reset`."""
    if locale not in SUPPORTED:
        locale = DEFAULT
    return _locale_var.set(locale)


def reset_request_locale(token: object) -> None:
    _locale_var.reset(token)  # type: ignore[arg-type]


def http_error(status: int, key: str, **params: object) -> HTTPException:
    """Build a localized HTTPException using the current request locale."""
    return HTTPException(status, translate(key, current_locale(), **params))


async def locale_middleware(request: Request, call_next):
    """ASGI middleware: set the locale contextvar per request.

    Wire once in `app.main` with `app.middleware("http")(locale_middleware)`.
    """
    locale = resolve_error_locale(request.headers.get("accept-language"))
    token = set_request_locale(locale)
    try:
        return await call_next(request)
    finally:
        reset_request_locale(token)


__all__ = [
    "DEFAULT",
    "ERRORS",
    "SUPPORTED",
    "current_locale",
    "http_error",
    "locale_middleware",
    "reset_request_locale",
    "resolve_error_locale",
    "set_request_locale",
    "translate",
]
