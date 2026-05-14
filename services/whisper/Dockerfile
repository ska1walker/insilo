# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS runtime

# Audio decoding deps + ffmpeg for non-WAV inputs
RUN apt-get update \
 && apt-get install -y --no-install-recommends libsndfile1 ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Non-root user (Olares deployment-whisper.yaml runs as uid 1000)
RUN groupadd -g 1000 insilo && useradd -u 1000 -g insilo -m -s /bin/false insilo

WORKDIR /app

# Install deps first (better layer cache) — only pyproject.toml + a tiny shim
COPY pyproject.toml ./
COPY app ./app

# Force CPU-only torch wheel — otherwise pip would pull CUDA libs (~2 GB extra).
# Order matters: torch first, then the rest can use the already-installed
# torch as a satisfied dependency.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      "torch>=2.2.0" \
 && pip install --no-cache-dir .

# Cache for downloaded model weights — Olares mounts /app/cache here
# whisper/ — faster-whisper model
# spkrec-ecapa/ — SpeechBrain speaker-embedding model (Phase A diarization)
RUN mkdir -p /app/cache/whisper /app/cache/spkrec-ecapa \
 && chown -R insilo:insilo /app/cache /app

USER insilo
ENV PYTHONPATH=/app
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
