"""
Insilo Backend - FastAPI Application Entry Point.

Wichtig: Wir implementieren KEINE eigene Authentifizierung.
Der Envoy-Sidecar vor diesem Container hat Authelia-Tokens bereits geprüft.
Die User-Identität kommt aus dem Header X-Bfl-User.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# from app.config import settings
# from app.db import init_db, close_db
# from app.routers import meetings, templates, search, admin


# ----------------------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & Shutdown."""
    # await init_db()
    yield
    # await close_db()


app = FastAPI(
    title="Insilo API",
    description="Souveräne Meeting-Intelligenz für deutschen Mittelstand",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ----------------------------------------------------------------------------
# Middleware
# ----------------------------------------------------------------------------

# CORS ist eher locker, weil Envoy davor schon filtert
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # auf der Olares-Box: alles intern, Envoy schützt
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------------
# Olares Auth Dependency
# ----------------------------------------------------------------------------

class CurrentUser(BaseModel):
    """User-Identität aus Olares-Header."""

    olares_username: str
    # Diese Felder werden später beim DB-Lookup gefüllt:
    # user_id: UUID
    # display_name: str
    # active_org_id: UUID


async def get_current_user(
    x_bfl_user: str | None = Header(None, alias="X-Bfl-User"),
) -> CurrentUser:
    """
    Liest die User-Identität aus dem Olares-Authelia-Header.

    Der Envoy-Sidecar vor diesem Container hat den Token bereits validiert.
    Wenn dieser Header fehlt, kommt der Request nicht durch die normale
    Olares-Auth-Pipeline — wir brechen ab.
    """
    if not x_bfl_user:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Bfl-User header. This API can only be called via Olares Envoy.",
        )

    # TODO: Olares-Username im DB-Users-Mapping nachschlagen (oder neu anlegen)
    return CurrentUser(olares_username=x_bfl_user)


# ----------------------------------------------------------------------------
# Health Endpoints
# ----------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    """Liveness-Probe für Kubernetes."""
    return {"status": "ok", "service": "insilo-backend"}


@app.get("/health/db")
async def health_db() -> dict:
    """DB-Verbindung prüfen."""
    # TODO: SELECT 1 gegen Olares-System-Postgres
    return {"status": "ok", "service": "postgres"}


@app.get("/health/whisper")
async def health_whisper() -> dict:
    """Whisper-Service erreichbar?"""
    # TODO: GET http://insilo-whisper:8001/health
    return {"status": "ok", "service": "whisper"}


@app.get("/health/ollama")
async def health_ollama() -> dict:
    """Ollama-Service erreichbar?"""
    # TODO: GET http://insilo-ollama:11434/
    return {"status": "ok", "service": "ollama"}


@app.get("/health/embeddings")
async def health_embeddings() -> dict:
    """Embeddings-Service erreichbar?"""
    # TODO: GET http://insilo-embeddings:8002/health
    return {"status": "ok", "service": "embeddings"}


# ----------------------------------------------------------------------------
# Root
# ----------------------------------------------------------------------------

@app.get("/")
async def root(user: CurrentUser = Depends(get_current_user)) -> dict:
    """API-Wurzel. Bestätigt nur, dass die Auth funktioniert."""
    return {
        "service": "insilo",
        "version": "0.1.0",
        "user": user.olares_username,
    }


# ----------------------------------------------------------------------------
# Router (kommt in Phase 1)
# ----------------------------------------------------------------------------

# app.include_router(meetings.router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
# app.include_router(templates.router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
# app.include_router(search.router, prefix="/api/v1", dependencies=[Depends(get_current_user)])
# app.include_router(admin.router, prefix="/api/v1/admin", dependencies=[Depends(get_current_user)])
