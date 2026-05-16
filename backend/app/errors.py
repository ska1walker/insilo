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

SUPPORTED: tuple[str, ...] = ("de", "en", "fr", "es", "it")
DEFAULT: str = "de"

ERRORS: dict[str, dict[str, str]] = {
    # ── tags ────────────────────────────────────────────────────────
    "tags.invalid_color": {
        "de": "Ungültige Farbe: {color} (erwartet wird #RRGGBB).",
        "en": "Invalid colour: {color} (expected #RRGGBB).",
        "fr": "Couleur invalide : {color} (format attendu : #RRGGBB).",
        "es": "Color no válido: {color} (se espera #RRGGBB).",
        "it": "Colore non valido: {color} (formato atteso: #RRGGBB).",
    },
    "tags.name_empty": {
        "de": "Name darf nicht leer sein.",
        "en": "Name must not be empty.",
        "fr": "Le nom ne peut pas être vide.",
        "es": "El nombre no puede estar vacío.",
        "it": "Il nome non può essere vuoto.",
    },
    "tags.duplicate": {
        "de": "Tag „{name}\" existiert bereits.",
        "en": "Tag '{name}' already exists.",
        "fr": "L'étiquette « {name} » existe déjà.",
        "es": "La etiqueta «{name}» ya existe.",
        "it": "Il tag «{name}» esiste già.",
    },
    "tags.not_found": {
        "de": "Tag nicht gefunden.",
        "en": "Tag not found.",
        "fr": "Étiquette introuvable.",
        "es": "Etiqueta no encontrada.",
        "it": "Tag non trovato.",
    },
    # ── meetings ───────────────────────────────────────────────────
    "meeting.not_found": {
        "de": "Besprechung nicht gefunden.",
        "en": "Meeting not found.",
        "fr": "Réunion introuvable.",
        "es": "Reunión no encontrada.",
        "it": "Riunione non trovata.",
    },
    "meeting.no_transcript": {
        "de": "Noch kein Transkript verfügbar.",
        "en": "No transcript available yet.",
        "fr": "Aucune transcription disponible pour l'instant.",
        "es": "Aún no hay transcripción disponible.",
        "it": "Trascrizione non ancora disponibile.",
    },
    "meeting.no_fields": {
        "de": "Keine Felder zum Aktualisieren angegeben.",
        "en": "No fields to update.",
        "fr": "Aucun champ à mettre à jour.",
        "es": "Ningún campo para actualizar.",
        "it": "Nessun campo da aggiornare.",
    },
    "meeting.invalid_speaker_id": {
        "de": "Ungültige Sprecher-ID: {sid}",
        "en": "Invalid speaker id: {sid}",
        "fr": "Identifiant de locuteur invalide : {sid}",
        "es": "ID de hablante no válido: {sid}",
        "it": "ID parlante non valido: {sid}",
    },
    "meeting.duplicate_speaker_id": {
        "de": "Doppelte Sprecher-ID: {sid}",
        "en": "Duplicate speaker id: {sid}",
        "fr": "Identifiant de locuteur en double : {sid}",
        "es": "ID de hablante duplicado: {sid}",
        "it": "ID parlante duplicato: {sid}",
    },
    "meeting.unknown_speaker_ref": {
        "de": "Segment {idx} verweist auf unbekannten Sprecher {sid}.",
        "en": "Segment {idx} references unknown speaker {sid}.",
        "fr": "Le segment {idx} référence un locuteur inconnu {sid}.",
        "es": "El segmento {idx} hace referencia a un hablante desconocido {sid}.",
        "it": "Il segmento {idx} fa riferimento al parlante sconosciuto {sid}.",
    },
    "meeting.invalid_language": {
        "de": "Ungültige Aufnahmesprache: {lang} (erwartet wird auto, de, en, fr, es oder it).",
        "en": "Invalid recording language: {lang} (expected auto, de, en, fr, es or it).",
        "fr": "Langue d'enregistrement invalide : {lang} (attendu : auto, de, en, fr, es ou it).",
        "es": "Idioma de grabación no válido: {lang} (se espera auto, de, en, fr, es o it).",
        "it": "Lingua di registrazione non valida: {lang} (atteso: auto, de, en, fr, es o it).",
    },
    # ── templates ──────────────────────────────────────────────────
    "template.not_found": {
        "de": "Vorlage nicht gefunden.",
        "en": "Template not found.",
        "fr": "Modèle introuvable.",
        "es": "Plantilla no encontrada.",
        "it": "Modello non trovato.",
    },
    "template.not_available": {
        "de": "Vorlage ist nicht verfügbar.",
        "en": "Template not available.",
        "fr": "Modèle non disponible.",
        "es": "Plantilla no disponible.",
        "it": "Modello non disponibile.",
    },
    "template.system_locked": {
        "de": "System-Vorlagen können nicht gelöscht werden.",
        "en": "System templates cannot be deleted.",
        "fr": "Les modèles système ne peuvent pas être supprimés.",
        "es": "Las plantillas del sistema no se pueden eliminar.",
        "it": "I modelli di sistema non possono essere eliminati.",
    },
    # ── auth / api keys ───────────────────────────────────────────
    "auth.invalid_key": {
        "de": "Ungültiger API-Schlüssel.",
        "en": "Invalid API key.",
        "fr": "Clé API invalide.",
        "es": "Clave API no válida.",
        "it": "Chiave API non valida.",
    },
    "auth.missing_scope": {
        "de": "Fehlender Scope: {scope}",
        "en": "Missing scope: {scope}",
        "fr": "Portée manquante : {scope}",
        "es": "Alcance ausente: {scope}",
        "it": "Scope mancante: {scope}",
    },
    # ── upstream services ─────────────────────────────────────────
    "service.embeddings_unreachable": {
        "de": "Embedding-Service nicht erreichbar.",
        "en": "Embeddings service unreachable.",
        "fr": "Service d'embeddings inaccessible.",
        "es": "Servicio de embeddings no accesible.",
        "it": "Servizio di embedding non raggiungibile.",
    },
    "service.llm_unreachable": {
        "de": "Sprachmodell nicht erreichbar.",
        "en": "LLM unreachable.",
        "fr": "Modèle linguistique inaccessible.",
        "es": "Modelo de lenguaje no accesible.",
        "it": "Modello linguistico non raggiungibile.",
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
