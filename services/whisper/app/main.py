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

from app.diarize import diarize, load_embedder, load_vad


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

    # Diarization (Phase A) — anonyme Sprecher-Labels per ECAPA-TDNN.
    # Beim Erst-Start lädt SpeechBrain ~60 MB Modell-Gewichte.
    diarization_enabled: bool = True
    diarization_cache_dir: str = "/app/cache/spkrec-ecapa"

    host: str = "0.0.0.0"
    port: int = 8001


settings = Settings()
log = logging.getLogger("insilo.whisper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class Segment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None       # anonymes Label, e.g. "SPEAKER_00"
    cluster_idx: int | None = None   # 0,1,2,… für das Org-Matching im Backend


class TranscribeResponse(BaseModel):
    language: str
    duration: float
    full_text: str
    segments: list[Segment]
    model: str
    # Pro erkanntem Cluster ein L2-normalisiertes Centroid (192 floats).
    # Reihenfolge = sortierte Cluster-Indices, also entspricht
    # centroids[i] dem Cluster mit cluster_idx == i.
    cluster_centroids: list[list[float]] = []


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
    if settings.diarization_enabled:
        try:
            os.makedirs(settings.diarization_cache_dir, exist_ok=True)
            load_embedder(settings.diarization_cache_dir)
            load_vad()
        except Exception as exc:
            # Diarization ist nice-to-have — wenn einer der drei Stages
            # nicht laden will, fallen wir auf "keine Sprecher-Labels"
            # zurück. Whisper läuft normal weiter.
            log.exception("speaker diarization failed to load: %s", exc)
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

        # Phase A: speaker diarization über die jetzt vorliegenden
        # Segmente. Bei Fehler oder deaktivierter Diarization lassen wir
        # speaker=None — Frontend zeigt dann generische Labels.
        centroids: list[list[float]] = []
        if settings.diarization_enabled and segments:
            try:
                result = diarize(
                    tmp.name,
                    [(s.start, s.end) for s in segments],
                )
                for seg, label, cidx in zip(
                    segments, result.speaker_labels, result.cluster_indices,
                    strict=False,
                ):
                    seg.speaker = label
                    seg.cluster_idx = cidx
                centroids = result.cluster_centroids
            except Exception as exc:
                log.exception("diarization failed: %s", exc)

    return TranscribeResponse(
        language=info.language,
        duration=float(info.duration),
        full_text=" ".join(s.text for s in segments).strip(),
        segments=segments,
        model=settings.model,
        cluster_centroids=centroids,
    )
