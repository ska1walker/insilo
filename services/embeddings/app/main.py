"""
Insilo embeddings service.

A FastAPI wrapper around BGE-M3 via sentence-transformers. Backend workers
POST text chunks here and receive 1024-dim vectors. Multilingual (DE/EN
primarily), Apache 2.0.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sentence_transformers import SentenceTransformer


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # BGE-M3 yields 1024-dim vectors and is multilingual.
    model: str = "BAAI/bge-m3"

    # "cpu" works everywhere; "mps" on Apple Silicon; "cuda" on Olares GPU.
    device: str = "cpu"

    # Where downloaded weights are cached.
    cache_dir: str = "/app/cache/embeddings"

    # Truncate inputs to this many tokens to stay within model context.
    max_seq_length: int = 8192

    host: str = "0.0.0.0"
    port: int = 8002


settings = Settings()
log = logging.getLogger("insilo.embeddings")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


_model: SentenceTransformer | None = None


def _load_model() -> SentenceTransformer:
    global _model
    if _model is None:
        os.makedirs(settings.cache_dir, exist_ok=True)
        log.info("loading embedding model %s on %s", settings.model, settings.device)
        _model = SentenceTransformer(
            settings.model,
            device=settings.device,
            cache_folder=settings.cache_dir,
        )
        if settings.max_seq_length:
            _model.max_seq_length = settings.max_seq_length
        log.info("model loaded, dim=%d", _model.get_sentence_embedding_dimension())
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_model()
    yield


app = FastAPI(
    title="Insilo Embeddings",
    description="BGE-M3 multilingual embedding microservice.",
    version="0.1.0",
    lifespan=lifespan,
)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=512)
    normalize: bool = True


class EmbedResponse(BaseModel):
    model: str
    dim: int
    vectors: list[list[float]]


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": settings.model,
        "device": settings.device,
        "loaded": _model is not None,
        "dim": _model.get_sentence_embedding_dimension() if _model else None,
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    if not req.texts:
        raise HTTPException(400, "texts must be non-empty")

    model = _load_model()
    vectors = model.encode(
        req.texts,
        normalize_embeddings=req.normalize,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return EmbedResponse(
        model=settings.model,
        dim=int(vectors.shape[1]),
        vectors=vectors.tolist(),
    )
