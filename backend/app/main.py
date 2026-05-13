"""
Insilo Backend - FastAPI Application Entry Point.

Auth: kein eigener Auth-Code. Auf Olares prüft der Envoy-Sidecar Authelia-Tokens
vor unserem Pod und injiziert die User-Identität über den Header X-Bfl-User.
Lokal mocken wir den Header im Frontend.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import CurrentUser, get_current_user
from app.db import close_pool, init_pool
from app.routers import audio, meetings, search, settings as settings_router, templates


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
    # TODO Phase 2: GET http://insilo-whisper:8001/health
    return {"status": "skipped", "service": "whisper", "reason": "phase 2"}


@app.get("/health/ollama")
async def health_ollama() -> dict:
    # TODO Phase 2: GET http://insilo-ollama:11434/
    return {"status": "skipped", "service": "ollama", "reason": "phase 2"}


@app.get("/health/embeddings")
async def health_embeddings() -> dict:
    # TODO Phase 3: GET http://insilo-embeddings:8002/health
    return {"status": "skipped", "service": "embeddings", "reason": "phase 3"}


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
