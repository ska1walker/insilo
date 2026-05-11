# Quickstart

> So startest du mit Claude Code in diesem Projekt — in ca. 15 Minuten.

---

## 1. Voraussetzungen installieren

```bash
# Node.js 20+ (für Frontend)
nvm install 20

# Python 3.11+ (für Backend)
pyenv install 3.11.10

# Docker & Docker Compose (für KI-Services)
# https://docs.docker.com/desktop/

# Supabase CLI (für lokale Datenbank)
brew install supabase/tap/supabase

# Claude Code
# https://docs.claude.com/en/docs/claude-code
```

---

## 2. Claude Code aktivieren

Beim ersten Start im Projektverzeichnis lädt Claude Code automatisch die `CLAUDE.md`. Zusätzlich diese Skills aktivieren:

```bash
# Im Projektverzeichnis
claude plugin add anthropic/frontend-design
claude plugin add nextlevelbuilder/ui-ux-pro-max-skill
```

**Prüfen:** `claude plugin list` sollte beide Skills zeigen.

---

## 3. Lokale Datenbank starten

```bash
cd supabase
supabase start
```

Das gibt dir `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` aus.

`.env`-Datei erstellen:
```bash
cp .env.example .env
# Werte aus `supabase status` eintragen
```

Migrations ausführen:
```bash
supabase db reset  # spielt 0001 + 0002 + seed automatisch ein
```

---

## 4. Frontend starten

```bash
cd frontend
npm install
npm run dev
```

→ http://localhost:3000

---

## 5. Backend (vorerst nur API-Skeleton) starten

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

→ http://localhost:8000/docs

---

## 6. KI-Services (Docker)

```bash
docker-compose up whisper ollama embeddings -d
```

Beim ersten Start dauern die Model-Downloads ~10-20 Min:
```bash
docker exec -it $(docker ps -qf name=ollama) ollama pull qwen2.5:14b-instruct-q4_K_M
```

---

## 7. Die ersten Claude-Code-Aufträge

Wenn Setup steht, sind das gute Startaufträge an Claude Code:

### Auftrag 1 — Box-Onboarding-Screen
> "Baue den Box-Onboarding-Screen gemäß `docs/DESIGN.md`. Der Nutzer gibt eine Server-URL ein oder scannt einen QR-Code. Validiere die URL durch einen GET auf `/health` und speichere bei Erfolg das Box-Profil in IndexedDB. Folge dem Designsystem strikt."

### Auftrag 2 — Aufnahme-Screen
> "Baue den Aufnahme-Screen. Großer goldener Recording-Button mittig, oben ein Timer in JetBrains Mono. Während aktiver Aufnahme: 1px goldene Pulse-Linie am oberen Bildschirmrand. Audio wird mit MediaRecorder API in 30s-Chunks aufgenommen und in IndexedDB gepuffert. Folge `docs/DESIGN.md` Abschnitt 6 für die Recording-Indicator-Logik."

### Auftrag 3 — Meeting-Liste
> "Baue den Meeting-Listen-Screen im PLAUD-Stil aus `docs/DESIGN.md` Abschnitt 5. Flache vertikale Liste, dünne Trennlinien, kein Card-Container. Pro Eintrag: Titel + Datum/Zeit + Dauer rechts. Daten kommen aus Supabase Realtime Subscription."

### Auftrag 4 — Backend Audio-Upload
> "Implementiere `POST /api/v1/recordings` in FastAPI. Chunked Resumable Upload, Validierung gegen Supabase Auth JWT, Schreiben in Supabase Storage Bucket `audio`. Schreibe einen Meeting-Record in der Datenbank mit Status `uploading` → nach erfolgreichem Upload `queued`. Stoße danach Celery-Task `transcribe_meeting` an."

---

## 8. Verzeichnis-Übersicht

```
insilo/
├── CLAUDE.md                ← Claude Code liest das zuerst
├── QUICKSTART.md            ← dieses Dokument
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
│
├── docs/
│   ├── ARCHITECTURE.md      ← Datenfluss, Komponenten
│   ├── DESIGN.md            ← Komplettes Designsystem
│   ├── ROADMAP.md           ← Phasen 1-6
│   ├── SECURITY.md          ← DSGVO, Verschlüsselung, Audit
│   └── DEPLOYMENT.md        ← Olares-Paketierung
│
├── frontend/                ← Next.js 15 PWA
│   ├── package.json
│   ├── tailwind.config.ts
│   └── public/manifest.json
│
├── backend/                 ← FastAPI
│   └── pyproject.toml
│
├── supabase/
│   ├── migrations/
│   │   ├── 0001_initial_schema.sql
│   │   └── 0002_rls_policies.sql
│   └── seed.sql             ← 4 System-Templates
│
└── olares/
    ├── OlaresManifest.yaml
    └── README.md
```

---

## 9. Wichtige Befehle (Cheat-Sheet)

```bash
# Frontend
cd frontend && npm run dev          # Dev-Server
cd frontend && npm run build        # Production-Build
cd frontend && npm run type-check   # TypeScript-Check

# Backend
cd backend && uvicorn app.main:app --reload
cd backend && celery -A app.workers.celery_app worker -l info
cd backend && ruff check .          # Linting
cd backend && pytest                # Tests

# Supabase
supabase start                       # Lokale Instanz starten
supabase status                      # Verbindungsinfos
supabase db reset                    # Schema neu aufsetzen
supabase migration new <name>        # Neue Migration

# Docker
docker-compose up -d                 # Alles starten
docker-compose logs -f backend       # Logs verfolgen
docker-compose down                  # Alles stoppen
```

---

## 10. Was wenn ich nicht weiterkomme?

1. **CLAUDE.md** und **ARCHITECTURE.md** zuerst lesen.
2. Sehr konkret formulieren: "Baue X gemäß DESIGN.md Abschnitt Y."
3. Bei Unklarheiten: Claude Code direkt fragen statt zu raten.
4. Bei Architektur-Entscheidungen: lieber einmal mehr rückversichern.
