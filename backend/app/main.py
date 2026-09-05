"""
Insilo Backend - FastAPI Application Entry Point.

Auth: kein eigener Auth-Code. Auf Olares prüft der Envoy-Sidecar Authelia-Tokens
vor unserem Pod und injiziert die User-Identität über den Header X-Bfl-User.
Lokal mocken wir den Header im Frontend.
"""

import logging
import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import audit, konfiguration
from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.db import acquire, acquire_als_dienst, close_pool, init_pool
from app.errors import locale_middleware
from app.llm_config import auth_header
from app.routers import (
    api_keys,
    audio,
    egress,
    external_api,
    locale,
    meetings,
    protokoll,
    search,
    speakers,
    tags,
    templates,
    webhooks,
)
from app.routers import settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()

    # Konfiguration zurücklesen, falls die Datenbank leer ist. Das ist der
    # Fall nach einer Neuinstallation: Olares legt die Datenbank dabei neu
    # an, während /app/data überlebt. Ohne das bekäme die Organisation eine
    # neue Kennung, und die vorhandenen Aufnahmen unter audio/<org-id>/
    # hätten niemanden mehr, zu dem sie gehören.
    try:
        async with acquire_als_dienst() as conn:
            if await konfiguration.wiederherstellen(conn):
                log.info("Konfiguration aus dem Datenverzeichnis übernommen")
            else:
                # Nichts wiederherzustellen — dann wenigstens einen
                # aktuellen Abzug hinterlassen, damit die erste
                # Sicherung nicht auf die erste Änderung warten muss.
                await konfiguration.sichern_leise(conn)
    except Exception as exc:  # noqa: BLE001
        # Weder Abzug noch Wiederherstellung dürfen den Start verhindern.
        log.warning("Konfigurations-Abzug beim Start übersprungen: %s", exc)

    if not settings.internal_token:
        log.warning(
            "INSILO_INTERNAL_TOKEN ist nicht gesetzt — das Backend nimmt Aufrufe "
            "aus dem Cluster ungeprüft an. In Betrieb legt der Helm-Chart das "
            "Geheimnis an; fehlt es dort, ist die App offen."
        )
    if settings.auto_provision:
        log.warning(
            "INSILO_AUTO_PROVISION ist an — ein unbekannter Name legt Nutzer und "
            "Organisation an. Nur für die Entwicklung gedacht."
        )

    yield
    await close_pool()


log = logging.getLogger(__name__)

app = FastAPI(
    title="Insilo API",
    description="Souveräne Meeting-Intelligenz für deutschen Mittelstand",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — locker, weil Olares Envoy davor sitzt. Lokal brauchen wir es für
# den Browser, der von http://localhost:3000 aus mit dem Backend redet.
# ---------------------------------------------------------------------------
# Konfigurations-Abzug nach jeder Änderung
#
# Eine Middleware statt eines Aufrufs in jedem Endpunkt: das deckt auch die
# Endpunkte ab, die es heute noch nicht gibt, und kann nicht an einer
# Stelle vergessen werden. Nur die Pfade, die wirklich Konfiguration
# ändern — eine Aufnahme hochzuladen soll keinen Abzug auslösen.
# ---------------------------------------------------------------------------

KONFIG_PFADE = ("/settings", "/webhooks", "/speakers", "/api-keys", "/templates")


@app.middleware("http")
async def konfig_abzug(request: Request, call_next):
    antwort = await call_next(request)
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and antwort.status_code < 400
        and any(p in request.url.path for p in KONFIG_PFADE)
    ):
        try:
            async with acquire_als_dienst() as conn:
                await konfiguration.sichern_leise(conn)
        except Exception as exc:  # noqa: BLE001
            # Der Abzug ist eine Bequemlichkeit, keine Bedingung. Die
            # Änderung steht bereits in der Datenbank.
            log.warning("Konfigurations-Abzug übersprungen: %s", exc)
    return antwort


# ---------------------------------------------------------------------------
# Protokoll — wer hat wann was geändert oder ausgeleitet
#
# Wie beim Abzug oben: eine Stelle, nicht zwölf. Was `audit.deuten` am
# Pfad erkennt, landet in `public.audit_log` — auch die Endpunkte, die es
# heute noch nicht gibt. Erfasst werden ändernde Aufrufe und die Wege, auf
# denen Inhalte die Box verlassen können; lesende Aufrufe der eigenen
# Oberfläche nicht (ein Protokoll, das jeden Seitenaufruf mitschreibt,
# beantwortet die Frage nicht mehr, für die es da ist).
# ---------------------------------------------------------------------------


@app.middleware("http")
async def protokoll_middleware(request: Request, call_next):
    vorgang = audit.deuten(request.method, request.url.path)
    if vorgang is None:
        return await call_next(request)

    try:
        antwort = await call_next(request)
    except Exception:
        # Auch ein Absturz ist ein Vorgang — und der interessanteste.
        await _protokoll_schreiben(request, vorgang, 500)
        raise

    await _protokoll_schreiben(request, vorgang, antwort.status_code)
    return antwort


async def _protokoll_schreiben(request: Request, vorgang, status: int) -> None:
    """Schreibt den Eintrag und lässt den Aufruf nie daran scheitern.

    Ein stiller Verlust wäre für ein Protokoll misslich, ein abgelehnter
    Aufruf wegen einer klemmenden Protokollzeile aber schlimmer: die
    Änderung steht dann bereits in der Datenbank. Deshalb `error` statt
    `warning` — das gehört gesehen, nicht überblättert.
    """
    try:
        async with acquire() as conn:
            await audit.aufzeichnen(
                conn,
                vorgang=vorgang,
                scope=request.scope,
                headers={k.lower(): v for k, v in request.headers.items()},
                client=request.client.host if request.client else None,
                status=status,
            )
    except Exception as exc:  # noqa: BLE001
        log.error("Protokoll-Eintrag für %s nicht geschrieben: %s", vorgang.aktion, exc)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Per-request locale resolution for user-facing error messages (v0.1.45+).
# Reads Accept-Language and stashes a DE/EN-supported locale in a
# contextvar that `app.errors.http_error` reads when building responses.
app.middleware("http")(locale_middleware)


# ---------------------------------------------------------------------------
# Torwächter — als letzte angemeldet, also die äußerste Schicht
#
# Das Backend hat bewusst keine Entrance und damit keinen Envoy-Sidecar:
# mit Sidecar bekamen die internen Aufrufe des Next.js-Servers keine
# Authelia-Cookies und liefen in 401 (Begründung im OlaresManifest,
# Abschnitt entrances). Der Preis war, dass `insilo-backend:8000` für
# **jeden Pod im Cluster** offen stand — und `X-Bfl-User` frei behauptbar
# war. Wer den Dienst erreichte, war, wer er zu sein behauptete.
#
# Das gemeinsame Geheimnis schließt die Lücke, ohne die Entrance
# zurückzuholen: der Helm-Chart legt es als Secret an und gibt es beiden
# Deployments; der Next.js-Server hängt es an jeden weitergereichten
# Aufruf. Ein Aufruf ohne gültiges Geheimnis wird abgewiesen, bevor
# `X-Bfl-User` überhaupt angesehen wird.
#
# Ausgenommen: die Health-Endpunkte (die Kubelet-Probes haben kein
# Geheimnis) und die externe Schnittstelle, die sich mit einem
# Zugriffsschlüssel ausweist und ihre Prüfung selbst mitbringt.
# ---------------------------------------------------------------------------

TORWAECHTER_FREI = (
    "/health",
    "/api/external/v1/",
    "/docs",
    "/redoc",
    "/openapi.json",
)


@app.middleware("http")
async def torwaechter(request: Request, call_next):
    if not settings.internal_token:
        # Nicht eingerichtet — offen, damit die lokale Entwicklung ohne
        # Aufbau läuft und ein Upgrade ohne Secret die App nicht bricht.
        # Beim Start steht der Hinweis im Protokoll.
        return await call_next(request)

    pfad = request.url.path
    if pfad.startswith(TORWAECHTER_FREI):
        return await call_next(request)

    mitgebracht = request.headers.get("X-Insilo-Internal", "")
    # Zeitkonstanter Vergleich: ein Vergleich, der beim ersten
    # abweichenden Zeichen abbricht, verrät das Geheimnis Zeichen für
    # Zeichen.
    if not secrets.compare_digest(mitgebracht, settings.internal_token):
        return JSONResponse(
            status_code=401,
            content={"detail": "This API is only reachable through the Insilo frontend."},
        )
    return await call_next(request)


# ----------------------------------------------------------------------------
# Health Endpoints (für Kubernetes-Probes + Frontend-Verbindungstest)
# ----------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "insilo-backend"}


@app.get("/health/db")
async def health_db() -> dict:
    async with acquire() as conn:
        await conn.fetchval("select 1")
    return {"status": "ok", "service": "postgres"}


@app.get("/health/whisper")
async def health_whisper() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.whisper_url}/health")
            return {"status": "ok" if r.status_code == 200 else "error", "service": "whisper"}
    except Exception as exc:
        return {"status": "error", "service": "whisper", "detail": str(exc)}


@app.get("/health/llm")
async def health_llm() -> dict:
    # Die wirksame Adresse steht pro Org in der Datenbank; die
    # Deployment-Vorgabe ist nur Rückfall und seit v0.1.72 regulär leer.
    # Ein Health-Check hat keinen Org-Kontext, also prüft er, ob überhaupt
    # irgendwo eine eingetragen ist — sonst meldete er „nicht
    # eingerichtet", während die App längst zusammenfasst.
    base = settings.llm_base_url
    key = settings.llm_api_key
    try:
        # Als Dienst, nicht ohne Kontext: `org_settings` steht seit
        # Migration 0017 unter erzwungener Zeilensicherheit. Ohne Kontext
        # sieht diese Abfrage null Zeilen und der Check meldete
        # „nicht eingerichtet", während die App längst zusammenfasst —
        # derselbe Widerspruch wie in v0.1.73, nur mit anderer Ursache.
        async with acquire_als_dienst() as conn:
            row = await conn.fetchrow(
                """
                select llm_base_url, llm_api_key
                from public.org_settings
                where trim(llm_base_url) <> ''
                limit 1
                """
            )
        if row:
            base = row["llm_base_url"]
            key = row["llm_api_key"] or key
    except Exception:  # noqa: BLE001
        # Datenbank nicht erreichbar — dafür gibt es /health/db. Hier
        # bleibt es beim Vorgabewert.
        pass

    if not base:
        return {"status": "not_configured", "service": "llm"}
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                f"{base.rstrip('/')}/models",
                headers=auth_header(key),
            )
            return {"status": "ok" if r.status_code < 500 else "error", "service": "llm"}
    except Exception as exc:
        return {"status": "error", "service": "llm", "detail": str(exc)}


@app.get("/health/stt")
async def health_stt() -> dict:
    """Spracherkennung — mitgelieferter Dienst oder externer Endpunkt.

    Ohne eingetragene Adresse ist das kein Mangel: dann transkribiert der
    Whisper-Dienst im eigenen Namespace, und kein Audio verlässt die Box.
    Deshalb meldet dieser Check in dem Fall den lokalen Dienst, nicht
    "nicht eingerichtet".
    """
    base = settings.stt_base_url
    key = settings.stt_api_key
    try:
        # Als Dienst — siehe /health/llm. Hier wiegt es schwerer: ohne
        # Kontext meldete der Check `mode=local` für eine Box, deren Ton
        # an einen externen Dienst geht. Eine Anwendung, die
        # Datensouveränität nachweist, darf den Weg nach draußen nicht
        # unterschlagen.
        async with acquire_als_dienst() as conn:
            row = await conn.fetchrow(
                """
                select stt_base_url, stt_api_key
                from public.org_settings
                where trim(stt_base_url) <> ''
                limit 1
                """
            )
        if row:
            base = row["stt_base_url"]
            key = row["stt_api_key"] or key
    except Exception:  # noqa: BLE001
        pass

    if not base:
        # Der Normalfall. /health/whisper prüft den lokalen Dienst selbst.
        return {"status": "ok", "service": "stt", "mode": "local"}
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(
                f"{base.rstrip('/')}/models",
                headers=auth_header(key),
            )
            r.raise_for_status()
        return {"status": "ok", "service": "stt", "mode": "external"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "service": "stt", "mode": "external", "detail": str(exc)}


@app.get("/health/embeddings")
async def health_embeddings() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.embeddings_url}/health")
            return {"status": "ok" if r.status_code == 200 else "error", "service": "embeddings"}
    except Exception as exc:
        return {"status": "error", "service": "embeddings", "detail": str(exc)}


# ----------------------------------------------------------------------------
# Root (smoke test for auth + auto-provisioning)
# ----------------------------------------------------------------------------

@app.get("/")
async def root(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {
        "service": "insilo",
        "version": "0.1.0",
        "user": user.olares_username,
        "org_id": str(user.org_id),
    }


# ----------------------------------------------------------------------------
# Routers
# ----------------------------------------------------------------------------

app.include_router(meetings.router)
app.include_router(templates.router)
app.include_router(search.router)
app.include_router(audio.router)
app.include_router(egress.router)
app.include_router(settings_router.router)
app.include_router(tags.router)
app.include_router(webhooks.router)
app.include_router(api_keys.router)
app.include_router(external_api.router)
app.include_router(speakers.router)
app.include_router(locale.router)
app.include_router(protokoll.router)
