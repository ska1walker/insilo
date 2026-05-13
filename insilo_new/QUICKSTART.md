# Quickstart — lokale Entwicklung

> Diese Anleitung zeigt, wie Insilo lokal entwickelt wird.
> Für das Olares-Deployment siehe [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).

---

## Voraussetzungen

- macOS oder Linux
- Docker Desktop oder vergleichbares
- Node.js 20+ (via nvm empfohlen)
- Python 3.11+
- (Optional) NVIDIA GPU für lokale KI-Tests — sonst nutzen wir Mocks

---

## 1. Repository klonen

```bash
git clone git@github.com:ska1walker/insilo.git
cd insilo
```

---

## 2. Umgebungsvariablen

```bash
cp .env.example .env
```

Standardwerte funktionieren für lokale Entwicklung.

---

## 3. Lokale Olares-Middleware-Emulation

Olares stellt PostgreSQL, KVRocks und MinIO als geteilte System-Services bereit. Lokal emulieren wir das mit Docker-Compose:

```bash
docker-compose up -d
```

Das startet:
- **PostgreSQL 16** mit pgvector und pg_trgm auf Port 5432
- **Redis 7** (KVRocks-kompatibel für lokale Dev) auf Port 6379
- **MinIO** auf Port 9000 (Console: 9001)

DB-Migrationen anwenden:

```bash
docker exec -i insilo_pg psql -U insilo -d insilo < supabase/migrations/0001_initial_schema.sql
docker exec -i insilo_pg psql -U insilo -d insilo < supabase/migrations/0002_rls_policies.sql
docker exec -i insilo_pg psql -U insilo -d insilo < supabase/seed.sql
```

---

## 4. Backend starten

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

API erreichbar unter `http://localhost:8000`.
Swagger-Docs: `http://localhost:8000/docs`.

**Wichtig für lokale Entwicklung:** Da Olares-Envoy-Sidecar lokal nicht existiert, mocken wir den `X-Bfl-User` Header. Im Browser-DevTools oder via Browser-Extension setzen, oder in der API-Doku manuell mitgeben.

---

## 5. Frontend starten

```bash
cd frontend
npm install
npm run dev
```

Frontend erreichbar unter `http://localhost:3000`.

---

## 6. KI-Services (optional, für Phase 2+)

### Ollama lokal

```bash
# macOS
brew install ollama
ollama serve
ollama pull qwen2.5:14b-instruct-q4_K_M
```

### faster-whisper lokal

```bash
pip install faster-whisper
# Modell wird beim ersten Aufruf automatisch geladen (~3 GB)
```

Phase 1 nutzt Mocks — diese Services brauchen wir erst ab Phase 2.

---

## 7. Tests

```bash
# Frontend
cd frontend && npm test

# Backend
cd backend && pytest
```

---

## 8. Olares-Paket lokal bauen (für Phase 4)

```bash
cd olares/..
cp -r olares insilo
tar -czf insilo-0.1.0.tgz insilo/
rm -rf insilo
```

Das `.tgz`-File kann dann via Olares **Studio → Upload custom chart** getestet werden.

---

## Häufige Probleme

### "Connection refused" beim Backend

PostgreSQL-Container läuft? Prüfen mit `docker ps`.

### "401 Unauthorized" im Frontend

`X-Bfl-User` Header fehlt. Browser-Extension setzen (z.B. ModHeader) oder im Code für Dev mocken.

### Frontend zeigt blanke Seite

Tailwind v4 ist neu — bei Build-Fehlern Cache löschen: `rm -rf .next && npm run dev`.

---

## Tipps für Claude Code

- Lies zuerst `CLAUDE.md` im Projekt-Root.
- Beachte: Wir bauen KEINE eigene Auth — Olares macht das.
- Designsystem ist verbindlich (`docs/DESIGN.md`).
- Bei Olares-Manifest-Fragen: `docs/DEPLOYMENT.md` und `olares/README.md` konsultieren.
