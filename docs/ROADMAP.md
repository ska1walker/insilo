# Roadmap

> Phasenplan vom MVP bis zum Markt-Launch.

---

## Phase 1 — Fundament (jetzt, ~3 Wochen)

**Ziel:** Lokale Dev-Umgebung läuft. Ein einfaches Meeting kann aufgenommen, transkribiert und angezeigt werden.

### Backend
- [ ] FastAPI-Projekt-Skeleton (`backend/app/`)
- [ ] Olares-Header-basierte User-Auth (X-Bfl-User)
- [ ] Datenbank-Schema (PostgreSQL Migrations)
- [ ] Audio-Upload-Endpoint (`POST /api/v1/recordings`)
- [ ] Celery + KVRocks-Setup
- [ ] faster-whisper Service als Container
- [ ] WebSocket-Server für Live-Updates
- [ ] Erste Transkriptions-Pipeline (ohne Diarization)

### Frontend
- [ ] Next.js 15 Projekt-Setup (`frontend/`)
- [ ] Tailwind v4 + shadcn/ui mit Design-Tokens
- [ ] PWA-Manifest + Service Worker
- [ ] Hauptscreen: Meeting-Liste
- [ ] Aufnahme-Screen mit MediaRecorder
- [ ] Meeting-Detail-Screen mit Transkript-View
- [ ] WebSocket-Client für Live-Updates

### Lokale Dev-Infrastruktur
- [ ] Docker-Compose mit PostgreSQL, KVRocks, MinIO (lokal — emuliert Olares-Middlewares)
- [ ] `.env.example` mit allen Variablen
- [ ] CI: Lint + Type-Check via GitHub Actions

**Meilenstein:** Audio-Upload → 5 Min später Transkript sichtbar (lokal).

---

## Phase 2 — Intelligenz (~2 Wochen)

**Ziel:** Strukturierte Notizen, Sprecher-Trennung.

- [ ] WhisperX Integration für Speaker Diarization
- [ ] Ollama-Service als Container
- [ ] Qwen 2.5 14B Modell-Pull
- [ ] LLM-Service mit FastAPI-Wrapper
- [ ] Template-System (DB-Schema + CRUD-API)
- [ ] System-Templates: "Allgemeine Besprechung", "Mandantengespräch", "Jahresgespräch"
- [ ] Summary-Worker (Celery-Task)
- [ ] Frontend: Zusammenfassungs-Tab
- [ ] Frontend: Template-Auswahl beim Meeting-Start

**Meilenstein:** Meeting wird automatisch mit gewähltem Template zusammengefasst.

---

## Phase 3 — Suche & Interaktion (~2 Wochen)

**Ziel:** "Ask"-Funktion über das Meeting-Archiv.

- [ ] BGE-M3 Embedding-Service
- [ ] Chunk-and-Embed-Worker
- [ ] pgvector-Index auf `meeting_chunks`
- [ ] Semantische Suche-API (`POST /api/v1/search`)
- [ ] RAG-Pipeline (Retrieval → Qwen 2.5)
- [ ] "Ask"-Tab im Frontend mit Chat-Interface
- [ ] Live-Transkription via WebSocket-Streaming
- [ ] Frontend: Live-Transkript-View während Aufnahme

**Meilenstein:** Nutzer kann seine 3-monatige Meeting-Historie befragen.

---

## Phase 4 — Olares-Paketierung (~2 Wochen)

**Ziel:** Insilo läuft als echtes Olares-App-Paket auf einer Test-Olares.

- [ ] Helm-Chart komplett (Chart.yaml, OlaresManifest.yaml, values.yaml, templates/)
- [ ] Multi-Container-Setup (Frontend, Backend, Worker, Whisper, Ollama, Embeddings)
- [ ] GPU-Resource-Definitionen
- [ ] Persistence-Volumes für /app/data und /app/cache
- [ ] Middleware-Integration: System-PostgreSQL + KVRocks
- [ ] Olares Studio: Dev-Test gegen eigene Olares-VM
- [ ] Markt-Upload mit `.tgz`-Validierung
- [ ] Installations-Doku für Endkunden
- [ ] Admin-UI: erste Version

**Meilenstein:** Frische Olares → Insilo aus Markt installieren → läuft.

---

## Phase 5 — Pilot-Deployment (~Q1 2027)

**Ziel:** Erste Box steht beim ersten Kunden.

- [ ] Pilotkunde finden (via aimighty Vertrieb)
- [ ] Hardware bestellen (Olares One)
- [ ] Vorkonfiguration im Werkstatt-Modus
- [ ] Vor-Ort-Installation
- [ ] Schulungs-Workshop (2-3 Stunden)
- [ ] 30 Tage Hyper-Care-Phase
- [ ] Feedback sammeln, Backlog aktualisieren

**Meilenstein:** Erste echte Meeting-Notizen im Produktivbetrieb.

---

## Phase 6 — Skalierung (~ab Q2 2027)

**Ziel:** Wiederholbarer Verkaufsprozess.

- [ ] Update-Mechanismus testen (mit echten Update-Releases)
- [ ] Monitoring & Health-Dashboard für Kunden-Boxen
- [ ] Erweiterte Templates (Branchen-spezifisch)
- [ ] Custom-Vocabulary (Fachterminologie pro Kunde)
- [ ] Audit-Log-Viewer im Frontend
- [ ] Marketing-Material: Website, Case-Studies, Demo-Videos
- [ ] Vertriebs-Enablement für aimighty (Pitch-Deck, Demo-Skript)

---

## Bewusste Auslassungen (nicht im MVP)

- ❌ Mobile Native Apps — PWA reicht
- ❌ Cloud-Sync zwischen Boxen
- ❌ Externe AI-API-Fallbacks
- ❌ Eigenes Hardware-Design (Olares One reicht)
- ❌ Englische UI (kommt frühestens Phase 7)
- ❌ Eigene Sprachsynthese / TTS
- ❌ Mobile Native Recording (PWA macht das)
- ❌ Eigene Mikrofon-Hardware (Smartphone reicht — Unterschied zu PLAUD)
