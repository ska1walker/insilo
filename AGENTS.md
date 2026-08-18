# Insilo — AGENTS.md

> **Für AI-Agents (Claude, Cursor, Copilot, etc.)**
> Konsolidierte Projektdaten für kontextbewusstes Arbeiten.

---

## Projekt-Identität

| Feld | Wert |
|------|------|
| **Produkt** | Insilo — datensouveräne Meeting-Intelligenz |
| **Maintainer** | Kai Böhm (kaivo.studio) |
| **Vertrieb** | aimighty.de |
| **Plattform** | Olares OS (Kubernetes-basiert) |
| **Status** | Phase 1 — MVP |
| **Version** | v0.1.60 |
| **Repository** | github.com/ska1walker/insilo |
| **Branch** | main |
| **Sprache** | DE (Primär), EN, FR, ES, IT |

---

## Was wir bauen

**Insilo** ist eine On-Premise-Lösung für Meeting-Aufnahme, Transkription und KI-gestützte Zusammenfassung. Läuft komplett auf einer Olares-Box im Serverraum des Kunden.

**Kernversprechen:** Keine einzige Audiosekunde, kein Transkript, kein Suchindex verlässt jemals die Olares-Box.

**Zielsegment:** Kanzleien, Steuerberatungen, Beratungen, Industrie-Mittelstand mit Compliance-Druck.

---

## Tech-Stack

### Frontend
- **Framework:** Next.js 15 (App Router, RSC)
- **Sprache:** TypeScript (strict mode)
- **Styling:** Tailwind CSS v4 + shadcn/ui
- **Icons:** Lucide React
- **State:** Zustand (lokal) + TanStack Query (Server-State)
- **Audio:** MediaRecorder API + WebRTC für Live-Streaming
- **Offline:** Service Worker mit Workbox, IndexedDB
- **i18n:** next-intl (DE/EN/FR/ES/IT)

### Backend
- **API:** FastAPI 0.115+
- **Sprache:** Python 3.11+
- **Datenbank:** asyncpg + SQLAlchemy 2.x
- **Background-Jobs:** Celery mit KVRocks als Broker
- **Object Storage:** MinIO (boto3)

### KI-Services
- **Whisper:** `faster-whisper` mit `large-v3` Modell
- **Speaker Diarization:** pyannote.audio (über WhisperX)
- **LLM:** Ollama mit `qwen2.5:14b-instruct-q4_K_M`
- **Embeddings:** BGE-M3 (multilingual, Apache 2.0)

### Datenbank
- **PostgreSQL 16** (Olares-System-PostgreSQL)
- **Extensions:** vector, pg_trgm, pgcrypto, uuid-ossp
- **RLS:** Row-Level Security auf jede Tabelle

### Cache & Queue
- **KVRocks** statt Redis (Redis-API-kompatibel, disk-persistent)

---

## Olares-Constraints (KRITISCH)

1. **Keine eigene Authentifizierung.** Envoy-Sidecar validiert Tokens. User-ID aus `X-Bfl-User` Header.
2. **Keine `hostNetwork`, `NodePort`, `LoadBalancer`.** Nur `ClusterIP`-Services.
3. **Keine ClusterRole-Bindings.** Streng namespace-isoliert.
4. **Keine Cross-Namespace-Direktcalls.** Service Provider Pattern.
5. **Storage nur in:** `/app/data/`, `/app/cache/`, `/app/Home/`
6. **Image-Naming:** `^[a-z0-9]{1,30}$`. Folder, `metadata.name`, `metadata.appid`, `Chart.yaml.name` müssen identisch sein.
7. **Deployment-Template:** `metadata.name` = literaler App-Name. Kein `{{ .Release.Name }}`.
8. **DB-Connection-Vars:** Via Helm-Values injiziert. Nicht hardcoden.

---

## Verzeichnisstruktur

```
insilo/
├── CLAUDE.md                    # Claude Code Briefing
├── AGENTS.md                    # Diese Datei — konsolidierte Projektdaten
├── OlaresManifest.yaml          # Olares App-Manifest
├── docker-compose.yml           # Lokale Dev-Umgebung
├── docs/                        # Dokumentation
│   ├── ARCHITECTURE.md          # System-Architektur
│   ├── DESIGN.md                # Design-System
│   ├── ROADMAP.md               # Phasen 1-6
│   ├── SECURITY.md              # Sicherheit
│   ├── DEPLOYMENT.md            # Olares-Paketierung
│   └── HANDOFF.md               # Lessons Learned
├── frontend/                    # Next.js 15 PWA
├── backend/                     # FastAPI
├── supabase/                    # NUR lokale Entwicklung
│   └── migrations/              # SQL-Migrationen
├── olares/                      # Helm-Chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
├── scripts/                     # Hilfs-Skripte
│   ├── check-chart.sh           # Chart-Validierung
│   ├── release.sh               # Release-Automatisierung
│   └── regen-migrations.py      # Migration-Mirror
└── services/                    # KI-Services
    ├── whisper/
    ├── embeddings/
    └── ollama/
```

---

## Designsystem

**Farben:** `#FFFFFF`, `#0A0A0A`, `#C9A961` (Gold, sehr sparsam)
**Typografie:** Lexend Deca (Display) + Inter (Body) + JetBrains Mono
**Anti-Patterns:** Keine Gradients, kein Glassmorphism, kein Lila, keine fetten Marketing-Headlines, keine AI-Sparkles

---

## Sprache & i18n

- **UI:** next-intl mit `useTranslations()` aus `frontend/messages/*.json`
- **Sprachen:** DE (Default), EN, FR, ES, IT
- **Anrede:** DE → Sie-Form; EN → "you"; FR → "vous"; ES → "usted"; IT → "Lei"
- **Code-Kommentare & Commits:** Englisch
- **Docs:** Deutsch

---

## Kernprinzipien

1. **Datensouveränität** ist nicht verhandelbar. Keine Telemetrie.
2. **Olares-native.** Nutze Plattform-Services statt eigene zu bauen.
3. **Multi-Tenant** von Anfang an. RLS in PostgreSQL.
4. **Offline-First** wo möglich. PWA-Cache für Meetings.
5. **Audit-Trail.** Jede Datenänderung wird geloggt.
6. **Reversibilität.** Soft-Delete + 30-Tage-Frist.
7. **Performance ist UX.** Background-Jobs + Progress-Indicators.
8. **Keep it boring.** Erprobte Pfade, keine Experimente.

---

## Phasenplan

| Phase | Status | Inhalt |
|-------|--------|--------|
| 1 | ✅ | Setup, Schema, Box-Onboarding, Aufnahme + Whisper-Transkription |
| 2 | 🚧 | LLM-Zusammenfassungen, Speaker Diarization, Template-System |
| 3 | 🔜 | "Ask"-Funktion (RAG), Live-Transkription |
| 4 | 🔜 | Olares-App-Paketierung, Markt-Upload |
| 5 | 🔜 | Pilot-Deployment, erste Kunden |
| 6 | 🔜 | Skalierung, Plattform-Erweiterung |

---

## Wichtige Skripte

| Skript | Zweck |
|--------|-------|
| `scripts/release.sh X.Y.Z` | Release-Automatisierung (bump, regen, check, commit, tag, push) |
| `scripts/check-chart.sh` | Chart-Validierung (Version-Sync, Drift-Check, lint) |
| `scripts/regen-migrations.py` | Mirror SQL-Migrationen nach `olares/files/` und regeneriert ConfigMap |

---

## CI/CD

- **GH Actions:** `ci.yml` (Tests, Linting, Chart-Checks)
- **Image-Build:** `release.yml` (GHCR-Push)
- **Tag-Regel:** `vX.Y.Z` muss `Chart.yaml.version` matchen
- **Deploy:** `kubectl set image` (Olares Box) oder Olares-Markt

---

## Olares Box (Production)

| Feld | Wert |
|------|------|
| **IP** | 192.168.112.125 |
| **SSH** | `olares@192.168.112.125` |
| **Namespace** | `insilo-kaivostudio` |
| **Pods** | insilo (frontend+envoy), insilo-backend, insilo-whisper, insilo-embeddings, insilo-worker |
| **Version** | v0.1.60 |

---

## Health Endpoints

| Endpoint | Service | Status |
|----------|---------|--------|
| `/health` | Backend | ok |
| `/health/db` | PostgreSQL | ok |
| `/health/whisper` | Whisper | ok |
| `/health/llm` | LiteLLM | ok |
| `/health/embeddings` | BGE-M3 | ok |

---

## Wichtige Dateien

| Datei | Beschreibung |
|-------|-------------|
| `CLAUDE.md` | Claude Code Briefing |
| `OlaresManifest.yaml` | Olares App-Manifest |
| `olares/Chart.yaml` | Helm Chart Metadata |
| `olares/values.yaml` | Helm Values |
| `frontend/messages/*.json` | i18n-Übersetzungen (5 Sprachen) |
| `backend/app/main.py` | FastAPI Entry Point |
| `backend/pyproject.toml` | Python Dependencies |
| `frontend/package.json` | Node Dependencies |

---

## Konventionen

- **Commit Messages:** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`)
- **Branches:** `main` (Production), Feature-Branches für Entwicklung
- **Tags:** `vX.Y.Z` (Semver)
- **Tests:** Vitest (Frontend), pytest (Backend)
- **Linting:** Ruff (Backend), ESLint (Frontend)
- **Type Checking:** mypy (Backend), tsc (Frontend)

---

## Was NICHT gebaut wird

- ❌ Eigene Authentifizierung (Olares macht das)
- ❌ Eigenes Supabase-Stack (PostgreSQL kommt von Olares)
- ❌ Mobile Native Apps (PWA reicht)
- ❌ Cloud-Sync zwischen Boxen (würde Kernversprechen brechen)
- ❌ Externe AI-API-Fallbacks
- ❌ Telemetrie & Tracking
- ❌ Marketplace für Templates (Phase 5+)

---

## Kontakt

- **Product & Code:** Kai Böhm (kaivo.studio)
- **Vertrieb:** aimighty.de
- **Hosting:** Kundenseitig (Olares-Box)
- **Infrastruktur:** Vercel + Supabase EU (nur Marketing/CRM, NICHT Kundendaten)
