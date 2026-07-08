"""
Insilo Backend - FastAPI Application Entry Point.

Auth: kein eigener Auth-Code. Auf Olares prüft der Envoy-Sidecar Authelia-Tokens
vor unserem Pod und injiziert die User-Identität über den Header X-Bfl-User.
Lokal mocken wir den Header im Frontend.
"""

from contextlib import asynccontextmanager

import httpx

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.db import close_pool, init_pool
from app.errors import locale_middleware
from app.routers import (
    api_keys,
    audio,
    external_api,
    locale,
    meetings,
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
    yield
    await close_pool()


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


# ----------------------------------------------------------------------------
# Health Endpoints (für Kubernetes-Probes + Frontend-Verbindungstest)
# ----------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "insilo-backend"}


@app.get("/health/db")
async def health_db() -> dict:
    from app.db import acquire

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
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                settings.llm_base_url.replace("/v1", ""),
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
            return {"status": "ok" if r.status_code < 500 else "error", "service": "llm"}
    except Exception as exc:
        return {"status": "error", "service": "llm", "detail": str(exc)}


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
app.include_router(settings_router.router)
app.include_router(tags.router)
app.include_router(webhooks.router)
app.include_router(api_keys.router)
app.include_router(external_api.router)
app.include_router(speakers.router)
app.include_router(locale.router)
