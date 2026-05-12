# Insilo — Projekt-Briefing für Claude Code

> **Produkt:** Insilo — datensouveräne Meeting-Intelligenz für deutschen Mittelstand
> **Maintainer:** Kai Böhm (kaivo.studio)
> **Vertrieb:** über aimighty.de
> **Plattform:** Olares OS (Kubernetes-basiert)
> **Status:** Phase 1 — MVP-Setup
> **Letzte Aktualisierung:** Mai 2026

---

## Was wir bauen

**Insilo** ist eine On-Premise-Lösung für Meeting-Aufnahme, Transkription und KI-gestützte Zusammenfassung. Sie läuft komplett auf einer Olares-Box im Serverraum des Kunden.

**Kernversprechen:** Keine einzige Audiosekunde, kein Transkript, kein Suchindex verlässt jemals die Olares-Box.

**Zielsegment:** Kanzleien, Steuerberatungen, Beratungen, Industrie-Mittelstand mit Compliance-Druck.

**Verkaufsargument gegen PLAUD/Otter/Fireflies:** Wir verzichten auf US-Cloud-AI. Alles lokal.

---

## Plattform-Kontext: Olares OS

Das ist die wichtigste Architekturentscheidung des Projekts. Olares OS ist kein "normales Linux", sondern ein **Kubernetes-basiertes Betriebssystem** mit strengen Constraints. Jede Code-Entscheidung muss sich daran ausrichten.

**Olares stellt bereit (wir bauen das NICHT selbst):**
- Authentifizierung & Autorisierung (Authelia + Envoy Sidecar)
- PostgreSQL 16 als geteilte System-Middleware
- KVRocks (Redis-kompatibel, disk-persistent) als geteilte Cache/Queue
- MinIO + JuiceFS für Object Storage
- NATS für Messaging
- TLS-Provisioning (Cloudflare Tunnel / Tailscale)
- Reverse Proxy & Routing
- Backup-Infrastruktur

**Insilo besteht aus:**
- Frontend (Next.js 15 PWA)
- Backend (FastAPI)
- Whisper-Service (faster-whisper auf GPU)
- Ollama-Container (Qwen 2.5 14B auf GPU)
- BGE-M3 Embedding-Service
- Celery-Worker für Background-Jobs

Alle laufen als separate Deployments im Namespace `insilo-<username>`, kommunizieren per Kubernetes-DNS.

---

## Olares-Constraints (für jede Code-Entscheidung)

Aus dem offiziellen Olares Deployment Guide:

1. **Keine eigene Authentifizierung implementieren.** Der Envoy-Sidecar vor jedem Pod validiert Tokens. Eingehende Requests an unsere Container sind bereits authentifiziert — trust them.

2. **Keine `hostNetwork`, kein `NodePort`, kein `LoadBalancer`.** Nur `ClusterIP`-Services. Externe Erreichbarkeit ausschließlich über deklarierte `entrances`.

3. **Keine ClusterRole-Bindings.** Wir sind streng auf den eigenen Namespace beschränkt.

4. **Keine Cross-Namespace-Direktcalls.** Wenn später eine andere App auf unsere Daten zugreifen will: Service Provider Pattern.

5. **Storage nur in drei Pfaden:**
   - `/app/data/` — persistent, überlebt Uninstall
   - `/app/cache/` — ephemer
   - `/app/Home/` — User-Files

6. **Image-Naming-Regel:** Olares-App-Name muss `^[a-z0-9]{1,30}$` matchen. **Folder-Name, `metadata.name`, `metadata.appid`, `Chart.yaml.name` müssen identisch sein.** Linter rejected sonst.

7. **Deployment-Template-Regel:** `metadata.name` muss der *literale* App-Name sein. `{{ .Release.Name }}` ist nicht erlaubt.

8. **Datenbank-Connection-Vars werden injiziert.** Wir bekommen `.Values.postgres.host`, `.Values.postgres.password` etc. zur Laufzeit. **Nicht hardcoden.**

---

## Tech-Stack

### Frontend (PWA)
- **Framework:** Next.js 15 (App Router, RSC)
- **Sprache:** TypeScript (strict mode)
- **Styling:** Tailwind CSS v4 + shadcn/ui
- **Icons:** Lucide React
- **State:** Zustand (lokal) + TanStack Query (Server-State)
- **Audio:** MediaRecorder API + WebRTC für Live-Streaming
- **Offline:** Service Worker mit Workbox, IndexedDB
- **PWA-Manifest:** standard

**Auth:** Wir nutzen **NICHT** Supabase Auth, NextAuth oder Ähnliches. Der Envoy-Sidecar von Olares prüft Authelia-Tokens, bevor Requests zu uns kommen. Die Benutzer-Identität bekommen wir aus dem Header `X-Bfl-User` (oder via Olares-API).

### Backend (FastAPI)
- **API:** FastAPI 0.115+
- **Sprache:** Python 3.11+
- **Datenbank-Client:** asyncpg + SQLAlchemy 2.x (kein Supabase-Client mehr)
- **Background-Jobs:** Celery mit KVRocks als Broker
- **Audio-Verarbeitung:** Aufruf an internen Whisper-Service
- **LLM-Calls:** Aufruf an internen Ollama-Service
- **Embeddings:** Aufruf an internen BGE-M3-Service

### KI-Services (jeweils eigener Container)
- **Whisper:** `faster-whisper` mit `large-v3` Modell
- **Speaker Diarization:** pyannote.audio (über WhisperX)
- **LLM:** Ollama mit `qwen2.5:14b-instruct-q4_K_M`
- **Embeddings:** BGE-M3 (multilingual, Apache 2.0)

### Datenbank-Strategie
**Olares-System-PostgreSQL nutzen, kein Supabase.** Begründung: weniger Container, native Integration, Olares verwaltet Backups/Updates. Connection-Variablen werden via Helm-Values injiziert.

Wir nutzen folgende Extensions (deklariert im OlaresManifest):
- `vector` — für pgvector (Embeddings)
- `pg_trgm` — für Trigram-Suche
- `pgcrypto` — für verschlüsselte Felder

### Cache & Queue
- **KVRocks** statt Redis. Redis-API-kompatibel, also Celery + python-redis-lib funktionieren weiterhin. Hauptvorteil: disk-persistent.

### Realtime an die PWA
Drei Optionen, MVP-Empfehlung: **WebSocket vom FastAPI-Backend** an die PWA, intern PostgreSQL LISTEN/NOTIFY für DB-Events. Optional später: NATS-Anbindung.

---

## Multi-Box-Architektur

Trotz der Olares-Integration bleibt die PWA **box-agnostisch**: sie wird einmal gebaut, kann sich aber mit verschiedenen Olares-Boxen verbinden (für Berater, die mehrere Kunden betreuen).

Bei Olares ergibt sich die Box-URL automatisch aus dem Entrance:
```
https://insilo<routeID>.<username>.olares.com
```

Der Nutzer "hängt sich" über diese URL in die Box ein. Multi-Box-Support in der PWA: jede Box-URL bekommt ein eigenes IndexedDB-Profil (Slack-Workspace-Pattern).

---

## Verzeichnisstruktur

```
insilo/
├── CLAUDE.md                    # dieses Dokument
├── README.md
├── QUICKSTART.md
├── .env.example
├── .gitignore
├── docker-compose.yml           # nur für lokale Dev-Umgebung
│
├── docs/
│   ├── ARCHITECTURE.md          # System-Architektur, Datenfluss
│   ├── DESIGN.md                # Design-System (Weiß/Schwarz/Gold)
│   ├── ROADMAP.md               # Phasen 1-6
│   ├── SECURITY.md              # Sicherheit (Olares macht das meiste)
│   ├── DEPLOYMENT.md            # Olares-Paketierung, GHCR, Markt-Upload
│   └── PLATFORM.md              # Langfristige Multi-App-Vision
│
├── frontend/                    # Next.js 15 PWA
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── next.config.mjs
│   ├── Dockerfile
│   └── public/manifest.json
│
├── backend/                     # FastAPI
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── app/main.py
│
├── supabase/                    # NUR für lokale Entwicklung
│   ├── migrations/
│   │   ├── 0001_initial_schema.sql
│   │   └── 0002_extensions.sql
│   └── seed.sql
│
└── olares/                      # Helm-Chart für Olares-Markt
    ├── Chart.yaml
    ├── OlaresManifest.yaml
    ├── values.yaml
    ├── templates/
    │   ├── deployment-frontend.yaml
    │   ├── deployment-backend.yaml
    │   ├── deployment-whisper.yaml
    │   ├── deployment-ollama.yaml
    │   ├── deployment-embeddings.yaml
    │   ├── deployment-worker.yaml
    │   ├── service-frontend.yaml
    │   ├── service-backend.yaml
    │   └── ...
    └── README.md
```

---

## Designsystem (Kurzfassung — Vollversion in `docs/DESIGN.md`)

**Drei Anker:**
- HubSpot → Komponenten-Sprache, Spacing, Klarheit
- aimighty.de → Farbwelt (Weiß/Schwarz/Gold)
- PLAUD → App-Struktur, Reduktion, Hierarchie

**Informationsdichte:** PLAUD-reduzierte Hauptscreens, HubSpot-dichte Detailviews.

**Farben:** `#FFFFFF`, `#0A0A0A`, `#C9A961` (Gold, sehr sparsam).

**Typografie:** Lexend Deca (Display) + Inter (Body) + JetBrains Mono.

**Anti-Patterns:** Keine Gradients, kein Glassmorphism, kein Lila, keine fetten Marketing-Headlines, kein Card-in-Card, keine AI-Sparkles.

**Identitäts-Signatur:** Goldene 1px-Linie am oberen Bildschirmrand pulsiert während aktiver Aufnahme.

**Aktivierte Claude-Code-Skills:**
- `frontend-design` (Anthropic offiziell)
- `UI/UX Pro Max` (Community-Skill)

---

## Sprache & Schreibstil

- **Kunden-UI:** Sie-Form, formelles Deutsch
- **Microcopy:** sachlich, präzise, ohne Marketing-Sprech
- **Fehlermeldungen:** menschlich, lösungsorientiert
- **Code-Kommentare und commit messages:** Englisch
- **User-facing docs:** Deutsch
- **CLAUDE.md, ARCHITECTURE.md etc.:** Deutsch

---

## Kernprinzipien

1. **Datensouveränität ist nicht verhandelbar.** Keine Telemetrie. Kein Phone Home. Externe Schriften in Production self-hosten.

2. **Olares-native.** Nutze Plattform-Services (PostgreSQL, KVRocks, MinIO, Auth) statt eigene zu bauen.

3. **Multi-Tenant von Anfang an.** Mehrere User pro Olares-Box möglich. Row-Level Security in PostgreSQL.

4. **Offline-First wo möglich.** PWA muss Meetings im Cache anzeigen, auch wenn Box gerade nicht erreichbar.

5. **Audit-Trail.** Jede Datenänderung wird geloggt.

6. **Reversibilität.** Soft-Delete + 30-Tage-Frist vor Hard-Delete.

7. **Performance ist UX.** Background-Jobs + Progress-Indicators.

8. **Keep it boring.** Erprobte Pfade, keine bleeding-edge-Experimente.

---

## Phasenplan (Detail in `docs/ROADMAP.md`)

- **Phase 1 (jetzt):** Setup, Schema, Box-Onboarding, Aufnahme + Whisper-Transkription
- **Phase 2:** LLM-Zusammenfassungen, Speaker Diarization, Template-System
- **Phase 3:** "Ask"-Funktion (RAG), Live-Transkription
- **Phase 4:** Olares-App-Paketierung, Markt-Upload
- **Phase 5:** Pilot-Deployment, erste Kunden
- **Phase 6:** Skalierung, Plattform-Erweiterung

---

## Wie Claude Code in diesem Repo arbeitet

1. **Vor jeder Code-Entscheidung:** `docs/ARCHITECTURE.md` und Olares-Constraints aus dieser CLAUDE.md lesen.
2. **Bei UI-Arbeit:** Skills `frontend-design` + `UI/UX Pro Max` aktivieren. Designsystem strikt aus `docs/DESIGN.md`.
3. **Bei Backend-Änderungen:** Wir bauen *keine* Auth-Logik. Eingehende Requests sind authentifiziert via Envoy. User-ID kommt aus `X-Bfl-User` Header.
4. **Bei DB-Änderungen:** Erst Migration in `supabase/migrations/`, dann Frontend/Backend. RLS auf jede neue Tabelle.
5. **Bei Storage:** Nur `/app/data/`, `/app/cache/`, `/app/Home/`. Niemals beliebige Pfade.
6. **Bei Olares-Manifest-Änderungen:** Lese vollständigen Olares Deployment Guide (in Projekt-Root). Linter-Regeln strikt befolgen.
7. **Sprachregel:** UI-Texte Deutsch (Sie-Form). Code Englisch.
8. **Tests:** Vitest fürs Frontend, pytest fürs Backend. Kritische Pfade (Audio-Upload, Transkription) immer mit Tests.
9. **Bei Unsicherheit:** stoppen und Kai fragen.

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

## Kontakt / Ownership

- **Product & Code:** Kai Böhm (kaivo.studio)
- **Vertrieb:** aimighty.de
- **Hosting:** Kundenseitig (Olares-Box)
- **Eigene Infrastruktur:** Vercel + Supabase EU (nur für kaivo.studio Marketing/CRM, NICHT Kundendaten)
