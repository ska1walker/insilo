"""
Insilo Whisper service.

A thin FastAPI wrapper around faster-whisper. Backend workers POST raw audio
bytes to /transcribe and receive structured segment data back.

Olares deployment uses large-v3 on GPU. Local dev defaults to a smaller CPU
model so a Mac can still transcribe a short clip in a few seconds.
"""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from faster_whisper import WhisperModel
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Whisper model name as understood by faster-whisper.
    # Examples: tiny, base, small, medium, large-v3
    model: str = "tiny"

    # Device: "cpu" (universal), "cuda" (NVIDIA on Olares GPU node),
    # "auto" lets faster-whisper decide.
    device: str = "cpu"

    # Compute type: "int8" is fastest on CPU; "float16" on CUDA.
    compute_type: str = "int8"

    # Where downloaded model weights are cached (/app/cache on Olares).
    cache_dir: str = "/app/cache/whisper"

    host: str = "0.0.0.0"
    port: int = 8001


settings = Settings()
log = logging.getLogger("insilo.whisper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class Segment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None  # filled by diarization in Phase 2


class TranscribeResponse(BaseModel):
    language: str
    duration: float
    full_text: str
    segments: list[Segment]
    model: str


_model: WhisperModel | None = None


def _load_model() -> WhisperModel:
    global _model
    if _model is None:
        os.makedirs(settings.cache_dir, exist_ok=True)
        log.info(
            "loading whisper model %s on %s (compute_type=%s, cache=%s)",
            settings.model,
            settings.device,
            settings.compute_type,
            settings.cache_dir,
        )
        _model = WhisperModel(
            settings.model,
            device=settings.device,
            compute_type=settings.compute_type,
            download_root=settings.cache_dir,
        )
        log.info("model loaded")
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly load so the first request doesn't pay the download cost
    _load_model()
    yield


app = FastAPI(
    title="Insilo Whisper",
    description="faster-whisper microservice for the Insilo backend.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": settings.model,
        "device": settings.device,
        "loaded": _model is not None,
    }


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
) -> TranscribeResponse:
    """
    Transcribe an audio file. `language` is optional — if None, faster-whisper
    auto-detects. For Insilo we usually pass "de".
    """
    if not audio.filename:
        raise HTTPException(400, "audio file required")

    payload = await audio.read()
    if len(payload) == 0:
        raise HTTPException(400, "empty audio")

    # faster-whisper accepts a path or file-like; we use a tempfile because it
    # plays nicely with various container backends (libsndfile etc.).
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=True) as tmp:
        tmp.write(payload)
        tmp.flush()

        model = _load_model()
        segments_iter, info = model.transcribe(
            tmp.name,
            language=language,
            vad_filter=True,
            word_timestamps=False,
            beam_size=1,  # speed > absolute accuracy for dev; bump to 5 in prod via env
        )

        segments = [
            Segment(start=float(s.start), end=float(s.end), text=s.text.strip())
            for s in segments_iter
        ]

    return TranscribeResponse(
        language=info.language,
        duration=float(info.duration),
        full_text=" ".join(s.text for s in segments).strip(),
        segments=segments,
        model=settings.model,
    )
