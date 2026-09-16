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
    "meeting.export_forbidden": {
        "de": "Den Export aller Besprechungen dürfen nur Inhaberinnen und Verwaltende anstoßen.",
        "en": "Only owners and administrators may export all meetings.",
        "fr": "Seuls les propriétaires et les administrateurs peuvent exporter toutes les réunions.",
        "es": "Solo los propietarios y administradores pueden exportar todas las reuniones.",
        "it": "Solo i titolari e gli amministratori possono esportare tutte le riunioni.",
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
    "meeting.recording_in_trash": {
        "de": "Diese Aufnahme wurde schon gesendet und liegt als „{titel}“ im Papierkorb. Holen Sie sie dort zurück.",
        "en": "This recording was already sent and is in the trash as “{titel}”. Restore it from there.",
        "fr": "Cet enregistrement a déjà été envoyé et se trouve dans la corbeille sous « {titel} ». Restaurez-le depuis la corbeille.",
        "es": "Esta grabación ya se envió y está en la papelera como «{titel}». Restáurela desde allí.",
        "it": "Questa registrazione è già stata inviata e si trova nel cestino come «{titel}». La ripristini da lì.",
    },
    "meeting.audio_too_large": {
        "de": "Die Datei ist zu groß. Insilo nimmt Aufnahmen bis {max_mb} MB an.",
        "en": "The file is too large. Insilo accepts recordings up to {max_mb} MB.",
        "fr": "Le fichier est trop volumineux. Insilo accepte les enregistrements jusqu'à {max_mb} Mo.",
        "es": "El archivo es demasiado grande. Insilo acepta grabaciones de hasta {max_mb} MB.",
        "it": "Il file è troppo grande. Insilo accetta registrazioni fino a {max_mb} MB.",
    },
    "meeting.no_audio": {
        "de": "Zu dieser Besprechung liegt keine Aufnahme mehr vor — sie lässt sich deshalb nicht erneut verarbeiten. Transkript und Zusammenfassung bleiben erhalten.",
        "en": "There is no recording left for this meeting, so it cannot be processed again. The transcript and summary remain available.",
        "fr": "Il n'y a plus d'enregistrement pour cette réunion ; elle ne peut donc pas être retraitée. La transcription et le résumé restent disponibles.",
        "es": "Ya no existe una grabación de esta reunión, por lo que no se puede volver a procesar. La transcripción y el resumen se conservan.",
        "it": "Per questa riunione non è più disponibile una registrazione, quindi non può essere rielaborata. Trascrizione e riepilogo restano disponibili.",
    },
    "meeting.queue_unavailable": {
        "de": "Die Verarbeitung ließ sich nicht starten — der Hintergrunddienst ist gerade nicht erreichbar. Versuchen Sie es in einigen Minuten erneut.",
        "en": "Processing could not be started — the background service is currently unreachable. Please try again in a few minutes.",
        "fr": "Le traitement n'a pas pu démarrer : le service d'arrière-plan est momentanément injoignable. Réessayez dans quelques minutes.",
        "es": "No se pudo iniciar el procesamiento: el servicio en segundo plano no está disponible. Vuelva a intentarlo en unos minutos.",
        "it": "Non è stato possibile avviare l'elaborazione: il servizio in background non è raggiungibile. Riprovi tra qualche minuto.",
    },
    "meeting.already_running": {
        "de": "Diese Besprechung wird gerade verarbeitet. Warten Sie, bis der Lauf zu Ende ist.",
        "en": "This meeting is being processed right now. Please wait for the run to finish.",
        "fr": "Cette réunion est en cours de traitement. Veuillez attendre la fin de l'exécution.",
        "es": "Esta reunión se está procesando ahora mismo. Espere a que termine.",
        "it": "Questa riunione è in elaborazione. Attenda il termine dell'esecuzione.",
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
