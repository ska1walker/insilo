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
| **Version** | v0.1.73 (Repo und Box) |
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
- **LLM:** externer OpenAI-kompatibler Endpunkt (LiteLLM auf der Box),
  Adresse pro Org unter `/einstellungen` — **kein Vorgabewert**
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
    └── embeddings/       # kein Ollama — LLM kommt von außen
```

---

## Designsystem

**System:** AImighty-Designsystem (seit 18.8.2026). Token in
`frontend/app/globals.css`, Tailwind-Anbindung über
`frontend/tailwind.insilo.preset.js` (unveränderte Kopie der Lieferung).

**Farben:** Hanseatenblau trägt die Fläche, Gold zeichnet aus. Im
Dunkelmodus handelt Gold.
**Typografie:** Geist Sans + Geist Mono, selbst gehostet (kein CDN)
**Hülle:** Navigation · Inhalt · Ablage; mobil Navigation als untere Leiste
**Zielgrößen:** 40 px Zeiger / 44 px Berührung, ohne Ausnahme
**Zustände:** Farbe nie allein — immer Zeichen und Satz
**Anti-Patterns:** Keine Gradients, kein Glassmorphism, keine Parallaxe, keine AI-Sparkles

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
| **IP** | 192.168.1.17 |
| **SSH** | `olares@192.168.1.17` |
| **Namespace** | `insilo-kaivostudio` |
| **Pods** | insilo (frontend+envoy), insilo-backend, insilo-whisper, insilo-embeddings, insilo-worker |
| **Version** | v0.1.73, Helm-Rev 51 (verifiziert 19.8.2026) |

---

## Health Endpoints

| Endpoint | Service | Status |
|----------|---------|--------|
| `/health` | Backend | ok |
| `/health/db` | PostgreSQL | ok |
| `/health/whisper` | Whisper | ok |
| `/health/llm` | LLM-Endpunkt | ok · `not_configured`, solange keine Adresse eingetragen ist |
| `/health/embeddings` | BGE-M3 | ok |

---

## ⚠️ Der LLM-Endpunkt hat keinen Vorgabewert (seit v0.1.72)

**Der Chart bringt keine Adresse mit.** Absicht, nicht Lücke: die
öffentliche Adresse leitet sich aus der Olares-App-Kennung von LiteLLM
ab, die erst bei dessen Installation vergeben wird; ein Alias wie
`llm.<zone>` ist frei gewählt; und der clusterinterne Weg
(`http://litellm-svc.litellm-<user>.svc.cluster.local/v1`) **antwortet
nicht** — der Envoy-Sidecar davor verlangt einen Authelia-Token, den ein
Server-zu-Server-Aufruf nicht hat (400 „cannot get user name from
header", mit `X-Bfl-User` 401).

Tragfähig ist nur die öffentliche Adresse, einzutragen unter
`/einstellungen`. Bis dahin: Aufnahme und Transkription laufen,
Zusammenfassungen unterbleiben (die Besprechung bleibt auf
`transcribed`), `/health/llm` meldet `not_configured`.

**Ein leerer API-Schlüssel ist der Normalfall.** Die Kopfzeile entsteht
zentral in `llm_config.auth_header()` und entfällt ohne Schlüssel — ein
`Bearer ` mit leerem Wert ist kein gültiger Kopfwert und scheitert schon
vor dem Verbindungsaufbau. Nie wieder von Hand zusammensetzen.

Der Datenschutz-Nachweis erkennt die eigene Box über `OLARES_ZONE` und
wertet sie nicht als Fremdanbieter.

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
