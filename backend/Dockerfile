# syntax=docker/dockerfile:1.7
# ===========================================================================
# Insilo Backend (FastAPI)
#
# Wird sowohl für Backend als auch für Celery-Worker verwendet (selbes Image,
# unterschiedlicher CMD im Olares-Deployment).
# Läuft als non-root (UID 1000).
# ===========================================================================

FROM python:3.11-slim AS builder

WORKDIR /build

# System-Dependencies für asyncpg & co.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# pip + uv
RUN pip install --no-cache-dir --upgrade pip uv

# Dependencies installieren (app/ must exist for pyproject's package config)
COPY pyproject.toml ./
COPY app ./app
RUN uv pip install --system --no-cache .

# ===========================================================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Runtime-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root User (UID 1000 — Olares-konform)
RUN groupadd -g 1000 insilo && \
    useradd -u 1000 -g insilo -m -d /home/insilo insilo

# Python-Packages aus Builder kopieren
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# App-Code
COPY --chown=insilo:insilo app /app/app

# Schreibrechte für /app/data und /app/cache (werden von Olares gemounted)
RUN mkdir -p /app/data /app/cache && \
    chown -R insilo:insilo /app

USER insilo

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
