# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 insilo && useradd -u 1000 -g insilo -m -s /bin/false insilo

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

RUN mkdir -p /app/cache/embeddings && chown -R insilo:insilo /app/cache /app

USER insilo
ENV PYTHONPATH=/app
EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
