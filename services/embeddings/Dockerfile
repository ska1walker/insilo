# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 insilo && useradd -u 1000 -g insilo -m -s /bin/false insilo

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

# Install CPU-only torch FIRST from the dedicated PyTorch CPU index,
# so sentence-transformers doesn't drag in the CUDA wheels (~2 GB).
# BGE-M3 runs comfortably on CPU; the GPU on Olares stays free for
# Whisper + Ollama. This shrinks the image from ~2.8 GB to ~0.6 GB.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install --no-cache-dir .

RUN mkdir -p /app/cache/embeddings && chown -R insilo:insilo /app/cache /app

USER insilo
ENV PYTHONPATH=/app
EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
