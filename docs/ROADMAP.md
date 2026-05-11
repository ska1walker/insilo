# Roadmap

> Phasenplan vom MVP bis zum verkaufsfähigen Produkt.

---

## Phase 1 — Fundament (jetzt, ~2-3 Wochen)

**Ziel:** Lokale Dev-Umgebung läuft, ein einfaches Meeting kann aufgenommen, transkribiert und angezeigt werden.

### Backend
- [ ] FastAPI-Projekt-Skeleton (`backend/`)
- [ ] Supabase Self-Hosted aufsetzen (Docker Compose lokal)
- [ ] Schema-Migrations (orgs, users, meetings, transcripts)
- [ ] Auth-Endpoints über Supabase
- [ ] Audio-Upload-Endpoint (`POST /api/v1/recordings`)
- [ ] Celery + Redis für Background-Jobs
- [ ] faster-whisper Service als Container
- [ ] Erste Transkriptions-Pipeline (ohne Diarization)

### Frontend
- [ ] Next.js 15 Projekt-Setup (`frontend/`)
- [ ] Tailwind v4 + shadcn/ui mit Design-Tokens
- [ ] PWA-Manifest + Service Worker
- [ ] Box-Onboarding-Flow (URL eingeben, Login)
- [ ] Hauptscreen: Meeting-Liste
- [ ] Aufnahme-Screen mit MediaRecorder
- [ ] Meeting-Detail-Screen mit Transkript-View

### Infrastruktur
- [ ] Docker-Compose für lokale Dev (Backend + Supabase + Whisper)
- [ ] `.env.example` mit allen nötigen Variablen
- [ ] CI: Lint + Type-Check via GitHub Actions

**Meilenstein:** Audio-Upload → 5 Min später Transkript sichtbar.

---

## Phase 2 — Intelligenz (~2 Wochen)

**Ziel:** Aus Transkripten werden strukturierte Notizen. Sprecher werden unterschieden.

- [ ] WhisperX Integration für Speaker Diarization
- [ ] Ollama-Service als Container
- [ ] Qwen 2.5 14B Modell-Pull
- [ ] LLM-Service mit FastAPI-Wrapper
- [ ] Template-System (DB-Schema + CRUD-API)
- [ ] System-Templates: "Allgemeine Besprechung", "Mandantengespräch", "Jahresgespräch"
- [ ] Summary-Worker (Celery-Task)
- [ ] Frontend: Zusammenfassungs-Tab im Meeting-Detail
- [ ] Frontend: Template-Auswahl beim Meeting-Start

**Meilenstein:** Meeting wird automatisch mit gewähltem Template zusammengefasst, Sprecher sind benannt.

---

## Phase 3 — Suche & Interaktion (~2 Wochen)

**Ziel:** "Ask"-Funktion über das Meeting-Archiv. Live-Transkription.

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

## Phase 4 — Olares-Verpackung (~1-2 Wochen)

**Ziel:** Produkt ist als Olares-App-Paket installierbar.

- [ ] Olares-App-Manifest (`olares/OlaresManifest.yaml`)
- [ ] Multi-Container-Setup (Backend, Frontend, Whisper, Ollama, BGE, Supabase, Redis)
- [ ] GPU-Resource-Definitionen
- [ ] Persistence-Volumes für DB und Audio
- [ ] Olares Studio: Dev-Test gegen lokale Olares-VM
- [ ] Installations-Doku für Endkunden
- [ ] Admin-UI: erste Version (Nutzer-Verwaltung, Box-Status)

**Meilenstein:** Frische Olares-Instanz → App installieren → läuft.

---

## Phase 5 — Pilot-Deployment (~laufend)

**Ziel:** Erste Box steht beim ersten Kunden.

- [ ] Pilotkunde finden (via kaivo.studio / aimighty Vertrieb)
- [ ] Hardware bestellen (Olares One)
- [ ] Vorkonfiguration im Werkstatt-Modus
- [ ] Vor-Ort-Installation
- [ ] Schulungs-Workshop (2-3 Stunden)
- [ ] 30 Tage Hyper-Care-Phase
- [ ] Feedback-Sammlung + Backlog-Update

**Meilenstein:** Erste echte Meeting-Notizen werden im Produktivbetrieb erstellt.

---

## Phase 6 — Skalierung (~Q4 2026 ff.)

**Ziel:** Produkt wird breiter verkauft, Operations werden skaliert.

- [ ] Update-Mechanismus (Pull, Manual, Air-Gapped)
- [ ] Monitoring & Health-Dashboard für Kunde-Boxen
- [ ] Erweiterte Templates (Branchen-spezifisch)
- [ ] Custom-Vocabulary (Fachterminologie pro Kunde)
- [ ] Multi-Mandant-Verwaltung (Holdings, Beratungen)
- [ ] Optional: Eigene Mikrofon-Hardware (PLAUD-Style)
- [ ] Erste branchenspezifische Submarken/Templates

---

## Bewusste Auslassungen (Out of Scope MVP)

- ❌ Mobile Native Apps (iOS/Android) — PWA reicht
- ❌ Web-Version für Desktop-Use — Mobile-First
- ❌ Cloud-Sync zwischen Boxen
- ❌ Externe AI-API-Fallbacks
- ❌ Eigenes Vertriebsfrontend für aimighty (kommt von dort)
- ❌ Mehrsprachige UI außer Deutsch (Englisch erst ab Phase 6)
- ❌ Eigene Sprachsynthese / TTS
