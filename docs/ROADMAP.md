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

## Backlog — Konkrete Feature-Wünsche (aufgenommen 2026-09-03)

> Arbeitsliste konkreter Produktwünsche. Nicht phasengebunden — wird bei
> der Planung in die passenden Phasen eingeordnet. `[ ]` = offen.

### 1. Audio-Upload / Import bestehender Audiodateien
- [ ] Import-Flow für bestehende Audiodateien (Dateiauswahl bzw.
      Teilen-Sheet → Upload → Transkription), nicht nur Live-Aufnahme
- [ ] UI: Datei-Import auf dem Aufnahme-Screen bzw. Meeting-Liste
- [ ] Sonderfälle: große Dateien (Progress), Batch-Import, Metadaten
      (Titel, Datum, Sprache) beim Import
- [ ] Bestand prüfen: `POST /api/v1/recordings` nimmt bereits
      Multipart-Uploads (`UploadFile`) — es fehlt der Frontend-Pfad,
      kein Audio-Player zum Abspielen der importierten Datei nötig

### 2. Härten — Audio-Retention & Retry bei Pipeline-Fehlern
- [ ] Garantie: Schlägt ein Schritt nach der Aufnahme fehl
      (Transkription, Diarization, Summary), bleibt das Audio dauerhaft
      erhalten — keine Löschung durch Fehlerpfad oder Aufräum-Job
- [ ] Automatischer Retry (exponentieller Backoff) für fehlgeschlagene
      Transkriptionen
- [ ] Manueller Re-Transcribe im Frontend (analog zu
      `retry-summary`; bisher nur `POST /meetings/{id}/retry-summary`,
      kein Retry für die Transkription)
- [ ] Fehlerfall-Nachweis im Datenschutz-Nachweis: Audio verlässt die
      Box nicht, nur weil ein Schritt fehlschlug
- [ ] Wechselwirkung mit Soft-Delete / 30-Tage-Frist klären

### 3. Gruppieren von „Idee" — Tageszusammenfassung
- [ ] Alle als „Idee" aufgenommenen Files eines Tages (`/idee`,
      `quick_mode`, Schnellnotiz-Template) zu **einer** Notiz
      zusammenfassen
- [ ] Konfigurierbar unter Einstellungen (Gruppierung an/aus,
      ggf. Zeitpunkt der Zusammenfassung)
- [ ] Grenzfälle: leere Tage, Mix aus Idee + regulären Meetings,
      spätere Ergänzung am selben Tag

### 4. Sofortaufnahme (Autostart-Capture)
- [ ] Aufnahme startet beim Öffnen des „Sofortaufnahme"-Einstiegs
      automatisch (PWA-Shortcut/Home-Screen-Icon auf `/idee`, nicht das
      Dashboard)
- [ ] Modus: quick (Schnellnotiz, `quick_mode`), Default aktiv
- [ ] Setting pro Gerät (localStorage `insilo.autostartCapture`,
      off|quick) unter Einstellungen, kein Backend-Änderung
- [ ] „Verwerfen"-Button in der Quick-Capture während der Aufnahme
      (Abbruch ohne Upload) gegen versehentliche Autostart-Aufnahmen
- [ ] Webhook-Dispatch unverändert (wie quick_mode)
- [ ] i18n (5 Sprachen) + PWA-Shortcut in manifest.json
- [ ] Verifikation: type-check, build, lint, manueller Permission-Flow

### 5. Notizen an das Hermes-Agent-Wiki senden (Umsetzung klären)
- [ ] Notizen (Schnellnotizen/Ideen, Meeting-Summaries) ins LLM-Wiki von
      Hermes Agent übernehmen
- [ ] Vorschlag: Markdown-Export (existiert: `exports/markdown.py`) →
      `.md`-Datei → an Hermes senden → Hermes legt sie ins Wiki ab
- [ ] Zu klären: Zugriffsweg auf der Box — Hermes-CLI headless vs.
      HTTP-API des hermesagent-Pods vs. Wings/WebUI-API vs. Messaging-
      Bridge vs. Olares-Files/Drive-Ordner als Austausch
- [ ] Zu klären: Trigger (manuell je Notiz / nach Summary / Batch) +
      Hermes-Adresse/Token in den Insilo-Einstellungen
- [ ] Constraint: keine Cross-Namespace-Directcalls → nur über
      Entrance-URL/Middleware; Datenschutz-Nachweis (Hermes läuft auf
      der Box, nutzt aber ggf. externe LLMs)

### 6. Notiz an Open WebUI senden
- [ ] Notiz in Open WebUI ablegen — idealerweise als Notiz, alternativ
      als Wissen (Knowledge-Bibliothek, RAG)
- [ ] Ansatz: Open-WebUI-REST-API (`/api/v1/notes/*`, `/api/v1/knowledge/*`,
      Bearer-Auth per API-Key), Aufruf aus Insilo-Backend über die
      Olares-Entrance-URL
- [ ] Zu klären: Notiz vs. Wissen (Wissen = Chunking/RAG über LLM,
      Notiz = sichtbare Markdown-Notiz), eigene Knowledge-Collection pro
      Tag/Projekt, Trigger + Einstellungen

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
