# Architektur

> System-Architektur für Insilo auf Olares OS.
> Datenfluss, Komponenten, Deployment-Topologie, Plattform-Strategie.

---

## 1. Topologie auf hohem Niveau

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BEIM KUNDEN (Olares-Box)                        │
│                                                                         │
│   ┌────────────┐                                                       │
│   │ Mitarbeiter│                                                       │
│   │ Smartphone │ ──HTTPS──┐                                            │
│   │ (PWA)      │          │                                            │
│   └────────────┘          ▼                                            │
│                  ┌─────────────────────────────────────────────────┐  │
│                  │  Cloudflare Tunnel / Tailscale                  │  │
│                  └────────────────────┬────────────────────────────┘  │
│                                       ▼                                │
│                  ┌─────────────────────────────────────────────────┐  │
│                  │  Olares Gateway (Ingress)                       │  │
│                  │  Routes nach routeID → Namespace/Service        │  │
│                  └────────────────────┬────────────────────────────┘  │
│                                       ▼                                │
│                  ┌─────────────────────────────────────────────────┐  │
│                  │  Envoy Sidecar                                  │  │
│                  │  Prüft Authelia-Token  → forward an Container   │  │
│                  └────────────────────┬────────────────────────────┘  │
│                                       ▼                                │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │  Namespace: insilo-<username>                                 │   │
│   │  ┌─────────────┐  ┌─────────────┐                            │   │
│   │  │  frontend   │←─│  backend    │                            │   │
│   │  │  (Next.js)  │  │  (FastAPI)  │                            │   │
│   │  └─────────────┘  └──┬──────────┘                            │   │
│   │                      │                                        │   │
│   │       ┌──────────────┼──────────────┐                        │   │
│   │       ▼              ▼              ▼                        │   │
│   │  ┌─────────┐  ┌──────────┐  ┌──────────────┐                │   │
│   │  │ whisper │  │  ollama  │  │  embeddings  │                │   │
│   │  │  (GPU)  │  │   (GPU)  │  │   (BGE-M3)   │                │   │
│   │  └─────────┘  └──────────┘  └──────────────┘                │   │
│   │                                                              │   │
│   │       worker (Celery, kein eigener Service)                  │   │
│   └──────────────────┬───────────────────────────────────────────┘   │
│                      │ verbindet sich mit System-Middlewares          │
│                      ▼                                                 │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │  Namespace: os-system  (Olares-managed)                       │   │
│   │  ┌──────────────┐  ┌─────────┐  ┌────────┐  ┌──────────┐    │   │
│   │  │ PostgreSQL   │  │ KVRocks │  │  NATS  │  │  MinIO   │    │   │
│   │  │ + pgvector   │  │ (Redis) │  │        │  │ (JuiceFS)│    │   │
│   │  └──────────────┘  └─────────┘  └────────┘  └──────────┘    │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                                                                        │
│   ╳ KEIN Outbound zu Cloud-Diensten ╳                                 │
└────────────────────────────────────────────────────────────────────────┘
```

**Was sich gegenüber Standard-Kubernetes-Apps unterscheidet:**

1. **Envoy-Sidecar erledigt Auth.** Unsere Container müssen keine Login-Logik implementieren.
2. **Middlewares sind geteilte System-Services.** Wir requesten Zugriff, statt eigene zu starten.
3. **Strenge Namespace-Isolation.** Kein direkter Cross-App-Zugriff.

---

## 2. Datenfluss: Vom Mikrofon zur Notiz

```
1. AUFNAHME (PWA)
   ───────────────
   MediaRecorder API → WebM/Opus, Mono, 16 kHz
   Chunking: 30s-Chunks für Resilienz
   Lokales Caching in IndexedDB

2. UPLOAD
   ──────
   PWA → POST /api/v1/recordings/upload (chunked, resumable)
   User-Identität aus Olares-Header (X-Bfl-User)
   Audio landet in MinIO Bucket "insilo-audio"
   Erzeugt: meetings.id, meetings.status = "uploading"

3. JOB-DISPATCH
   ────────────
   Nach erfolgreichem Upload: Celery-Task "transcribe_meeting"
   Broker: KVRocks (Redis-API-kompatibel)
   meetings.status = "queued"
   PWA bekommt WebSocket-Update vom Backend

4. TRANSKRIPTION
   ─────────────
   Worker holt Audio aus MinIO
   HTTP-Call an internen Service:
     POST http://whisper.insilo-<user>.svc.cluster.local:8001/transcribe
   faster-whisper large-v3 + pyannote Diarization (GPU)
   Output: JSON mit segments[{start, end, speaker, text}]
   Speicherung: transcripts Tabelle (JSONB)
   meetings.status = "transcribed"

5. ZUSAMMENFASSUNG
   ────────────────
   Zweiter Task "summarize_meeting" startet automatisch
   System-Prompt aus templates Tabelle
   HTTP-Call:
     POST http://ollama.insilo-<user>.svc.cluster.local:11434/api/generate
   Modell: qwen2.5:14b-instruct-q4_K_M
   Strukturiertes JSON-Output gemäß Template-Schema
   Speicherung: summaries Tabelle (JSONB)

6. EMBEDDING & SUCHE
   ──────────────────
   Dritter Task "embed_meeting" parallel
   Chunking in semantische Einheiten (~500 Tokens)
   HTTP-Call:
     POST http://embeddings.insilo-<user>.svc.cluster.local:8002/embed
   BGE-M3 generiert Embeddings (1024-dim)
   Speicherung: meeting_chunks Tabelle mit pgvector

7. UI-UPDATE
   ──────────
   Backend pusht WebSocket-Message an PWA: "ready"
   meetings.status = "ready"
   User kann Transkript, Zusammenfassung, "Ask" nutzen
```

---

## 3. Komponenten-Verantwortlichkeiten

### Frontend (PWA)

**Macht:**
- Audio-Aufnahme mit MediaRecorder API
- Lokales Audio-Caching in IndexedDB (Offline-Aufnahme)
- Chunked Resumable Upload
- Live-Updates über WebSocket-Verbindung zum Backend
- Box-Profil-Verwaltung (Multi-Box-Support für Berater)
- Service Worker für Offline-Capability

**Macht NICHT:**
- Keine Authentifizierungs-Logik (Envoy + Authelia)
- Keine eigene Transkription
- Keine direkte DB-Verbindung
- Keine externen Calls außer zum eigenen Backend

### Backend (FastAPI)

**Macht:**
- REST-API für PWA
- WebSocket-Server für Live-Updates
- Audio-Upload-Handling, Validierung
- Job-Orchestrierung (Celery)
- DB-Zugriff via asyncpg/SQLAlchemy
- Admin-Endpoints (User-Management, Templates)

**Macht NICHT:**
- Keine Auth-Implementierung — User-Identität aus `X-Bfl-User` Header
- Keine direkten KI-Calls (alle async über Celery)

### KI-Services (separate Deployments)

**Whisper-Service**
- Container: Python 3.11 + faster-whisper + pyannote.audio
- Endpoint: `POST /transcribe` (Audio-Upload + JSON-Response)
- Modell: large-v3 (~3 GB) lokal in `/app/cache/models/`
- GPU: 1× NVIDIA, ~3 GB VRAM

**Ollama-Service**
- Container: offizielles `ollama/ollama:latest`
- Endpoint: HTTP-API auf Port 11434
- Modell: `qwen2.5:14b-instruct-q4_K_M` (~9 GB im VRAM)
- GPU: 1× NVIDIA, ~10 GB VRAM

**Embeddings-Service**
- Container: Python 3.11 + sentence-transformers
- Endpoint: `POST /embed` (Text-Array → 1024-dim Vektoren)
- Modell: BGE-M3 (~2 GB)
- CPU-only ist OK, GPU optional

**Worker (Celery)**
- Selbes Image wie Backend
- Lauscht auf KVRocks-Queue
- Orchestriert Transcribe → Summarize → Embed Pipeline

### Datenbank (Olares-System-PostgreSQL)

Wir bekommen vom System:
- Eigene Datenbank `insilo`
- Eigenen User `insilo` mit Passwort
- Aktivierte Extensions: `vector`, `pg_trgm`, `pgcrypto`, `uuid-ossp`
- Connection-Variablen werden in Container-Env injiziert

**Schema-Übersicht:**
```
orgs (Mandanten — eine Box kann mehrere Orgs hosten)
 └─ users
     └─ user_org_roles

meetings (Aufnahme + Metadaten)
 ├─ transcripts (1:1, JSONB Speaker-Segmente)
 ├─ summaries (1:n, mehrere Template-Outputs)
 └─ meeting_chunks (1:n, pgvector für RAG)

templates (Zusammenfassungs-Templates)
audit_log (alle sicherheitsrelevanten Aktionen)
```

Detail in `supabase/migrations/0001_initial_schema.sql`.

### Object Storage (Olares-System-MinIO)

- Bucket-Naming: `insilo-audio`, `insilo-exports`
- Zugriff über S3-API via MinIO-Client-Lib
- Connection via injizierte Env-Vars

### Cache & Queue (Olares-System-KVRocks)

- Redis-API-kompatibel (Celery, redis-py funktionieren)
- Disk-persistent: Jobs überleben Reboot
- Eigener Namespace `insilo` zur Trennung von anderen Apps

---

## 4. Authentifizierung & Identität

**Das ist anders als in normalen Web-Apps.**

### Was Olares macht (wir nutzen es)

1. Nutzer öffnet `https://insiloXXX.<user>.olares.com`
2. Cloudflare Tunnel terminiert TLS
3. Olares Gateway routet zu Envoy-Sidecar des Insilo-Frontends
4. Envoy prüft: Hat Request gültigen Authelia-Token?
   - Nein → Redirect zu Authelia Login (mit MFA)
   - Ja → forward an Frontend-Container
5. Frontend lädt, ruft Backend-API auf
6. Envoy-Sidecar vor Backend prüft erneut
7. Request kommt im Backend an mit injizierten Headers:
   ```
   X-Bfl-User: alice
   X-Auth-Subject: alice
   ```

### Was wir machen

Im Backend lesen wir den User aus dem Header:

```python
# app/dependencies/auth.py
from fastapi import Header, HTTPException

async def get_current_user(
    x_bfl_user: str = Header(None)
) -> str:
    if not x_bfl_user:
        raise HTTPException(401, "Missing auth header")
    return x_bfl_user
```

Das ist die *einzige* Auth-Logik im Backend. Kein JWT-Handling, kein Token-Refresh, kein Login-Endpoint.

### Mapping auf Org-Mitgliedschaft

```python
# Pseudo-Code
async def get_user_org(username: str) -> Org:
    # First-Login: User automatisch der Default-Org zuordnen
    # Mehr-Org-User: muss aktiven Org-Kontext mitschicken
    ...
```

Bei der ersten Aufnahme eines neuen Olares-Users legen wir automatisch einen Datensatz in unserer `users`-Tabelle an, mit Mapping zur Default-Org.

---

## 5. Externe Erreichbarkeit (Entrance Configuration)

Insilo hat **zwei Entrances**:

### Entrance 1: PWA (User-facing)

```yaml
entrances:
  - name: app
    host: insilo-frontend
    port: 3000
    title: "Insilo"
    authLevel: private          # MUSS auth-protected sein
    icon: https://...
```

Dies erzeugt eine URL wie `https://insilo-XXX.alice.olares.com` für die PWA.

### Entrance 2: Backend-API (für Frontend-Calls)

```yaml
entrances:
  - name: api
    host: insilo-backend
    port: 8000
    title: "Insilo API"
    authLevel: private
    invisible: true              # nicht im Desktop-Launcher anzeigen
```

Die API ist erreichbar, aber hat kein Icon auf dem Olares-Desktop.

**Wichtig:** Whisper, Ollama, Embeddings sind **interne Services ohne Entrance**. Sie sind nur namespace-intern per Kubernetes-DNS erreichbar.

---

## 6. Storage-Strategie

Alle persistenten Pfade folgen Olares-Konventionen:

| Pfad im Container         | Olares-Lifecycle | Inhalt                              |
|---------------------------|------------------|-------------------------------------|
| `/app/data/audio/`        | Persistent       | Audio-Originale (alternativ MinIO)  |
| `/app/data/models/`       | Persistent       | Vorgeladene Whisper-/BGE-Modelle    |
| `/app/cache/temp/`        | Ephemer          | Zwischen-Verarbeitungsdateien       |
| `/app/cache/uploads/`     | Ephemer          | Hochgeladene Chunks während Upload  |

**Empfehlung MVP:** Audio in MinIO statt `/app/data` — MinIO ist gemanaged, hat S3-API, leichteres Backup.

In `OlaresManifest.yaml`:
```yaml
permission:
  appData: true     # für /app/data
  appCache: true    # für /app/cache
```

---

## 7. Multi-Tenancy innerhalb einer Box

Eine Olares-Box kann mehrere Mandanten (Orgs) beherbergen. Wichtig für:
- Beratungen, die mehrere Klienten betreuen
- Holdings mit Tochtergesellschaften
- Mehrere Anwaltskanzleien in einer Bürogemeinschaft

### RLS-Pattern

Jede Tabelle mit Org-Daten hat:
```sql
-- Spalte
org_id UUID NOT NULL REFERENCES orgs(id)

-- RLS-Policy
CREATE POLICY meetings_org_isolation ON meetings
  FOR SELECT USING (
    org_id IN (
      SELECT org_id FROM user_org_roles
      WHERE user_id = current_setting('app.current_user_id')::uuid
    )
  );
```

Bei jeder DB-Verbindung setzen wir `app.current_user_id` aus dem Olares-Header. Das ist die *einzige* Stelle, wo wir den User-Kontext explizit setzen — danach kümmert sich Postgres-RLS um die Datenfilterung.

---

## 8. Performance-Erwartungen

| Operation                              | Erwartung (Olares One)    |
|----------------------------------------|---------------------------|
| Upload 60-Min-Meeting (50 MB)          | ~30 Sek bei LAN           |
| Transkription 60-Min-Meeting           | 4-7 Min (faster-whisper)  |
| Speaker Diarization 60-Min             | +2-3 Min                  |
| Zusammenfassung 60-Min-Transkript      | 30-60 Sek (Qwen 2.5)      |
| Embedding 60-Min-Transkript            | 10-20 Sek (BGE-M3)        |
| "Ask"-Query (RAG)                      | 1-3 Sek                   |
| **Aufnahme bis fertige Notiz (total)** | **~10 Min für 60-Min-Meeting** |

**Parallelität:** 2-3 gleichzeitige Aufnahmen ohne spürbare Verlangsamung.

---

## 9. Offline-Fähigkeit

**Was offline funktioniert (PWA):**
- Bereits geladene Meetings anschauen (Cache)
- Neue Aufnahme starten (lokal gepuffert)
- Notizen lesen, manuelle Markierungen

**Was offline NICHT geht:**
- Neue Transkription (braucht Box)
- Suche
- Login (Authelia ist auf der Box)

**Sync-Verhalten:** Wenn Box wieder erreichbar, werden gepufferte Aufnahmen hochgeladen. Konflikte: Last-Write-Wins, außer bei Notizen (Merge).

---

## 10. Update-Strategie

Olares hat eingebauten Update-Mechanismus via Markt. Drei Modi für Insilo-Updates:

**Modus 1: Markt-Update (Standard)**
- Wir laden neue `.tgz`-Pakete in den Olares-Markt
- Kunde sieht "Update verfügbar" in der Olares-Desktop-UI
- 1-Klick-Update durch Kunden-Admin

**Modus 2: Custom-Upload**
- Wir liefern signiertes `.tgz` per E-Mail/SFTP
- Kunde lädt es manuell hoch über *Market → Upload Custom Chart*

**Modus 3: Auto-Update (optional)**
- Kunde aktiviert Auto-Update in Olares
- Updates kommen täglich

**Wichtig:** Kein automatischer Pull zu kaivo.studio-Servern. Updates fließen ausschließlich über Olares-Markt oder manuelles File-Upload.

---

## 11. Plattform-Strategie (Multi-App-Vision)

> Wichtig: Insilo wird als **eigenständige App** im Olares-Markt veröffentlicht. Diese Sektion beschreibt die längerfristige Vision für ein Plattform-Portfolio.

### Das große Bild

kaivo.studio baut nicht eine App, sondern **eine Familie deutscher KI-Mittelstandsapps**, die auf Olares-Boxen koexistieren:

```
        Olares-Box beim Kunden Müller GmbH
   ┌─────────────────────────────────────────────┐
   │  kaivo.studio Apps (alle aus Olares-Markt)  │
   │                                             │
   │  ┌─────────┐  ┌──────────┐  ┌──────────┐  │
   │  │ Insilo  │  │ CallList │  │MaklerOS  │  │
   │  │(Meeting)│  │(Vertrieb)│  │(Brokerage)│ │
   │  └─────────┘  └──────────┘  └──────────┘  │
   │                                             │
   │  geteilte Olares-Middlewares:               │
   │  PostgreSQL, KVRocks, MinIO, NATS           │
   │                                             │
   │  geteilte Auth: Authelia + LLDAP            │
   └─────────────────────────────────────────────┘
```

### Wirtschaftlicher Sinn

**Vertrieb:** Wenn aimighty.de einmal eine Box verkauft hat, können weitere Apps mit minimalem Aufwand nachverkauft werden.

**Kosten:** Jede zusätzliche App teilt sich die Hardware. Marginalkosten gehen Richtung Null.

**Customer-Lifetime-Value:** Statt einmalig 12k€ für Insilo → 30k€/Jahr für drei Apps gemeinsam.

### Technische Voraussetzungen für Multi-App

1. **App-Naming-Konvention:** Alle kaivo-Apps müssen `^[a-z0-9]{1,30}$` einhalten. Vorschlag:
   - `insilo` — Meeting-Intelligenz
   - `calllist` — Mobiler Vertrieb (aus existierender App migriert)
   - `maklerOS` (nicht möglich wegen Großbuchstaben) → `maklerOS` nicht erlaubt → wir bräuchten z.B. `maklert`
   - **Konsequenz:** Wir brauchen für alle bestehenden kaivo-Apps neue olares-konforme Codenames

2. **Geteilte Auth.** Alle Apps nutzen denselben Olares-User. Mitarbeiter login einmal → alle Apps offen.

3. **Inter-App-Kommunikation via Service Provider Pattern.**

   Beispiel: CallList soll Insilo-Meeting-Notizen für einen Kunden-Kontakt anzeigen.

   **In Insilo's Manifest:**
   ```yaml
   provider:
     - name: insilo-meetings-api
       entrance: insilo-backend
       paths: ["/api/v1/meetings"]
       verbs: ["GET"]
   ```

   **In CallList's Manifest:**
   ```yaml
   permission:
     provider:
       - appName: insilo
         providerName: insilo-meetings-api
   ```

   Bei Installation muss der Endnutzer dieser Cross-App-Permission explizit zustimmen. Zur Laufzeit routet `system-server` die Calls und validiert die Permission.

4. **Konsistentes Design-System.** Alle kaivo-Apps nutzen denselben Stil (Weiß/Schwarz/Gold, HubSpot-Sprache, PLAUD-Reduktion). `docs/DESIGN.md` ist der Master.

### Roadmap der Plattform

- **Q1 2027:** Insilo Pilot bei 3 Kunden (Kanzleien)
- **Q2 2027:** Insilo Markt-Release, Vertriebsstart über aimighty
- **Q3 2027:** Zweite App im Portfolio (CallList-Migration oder neue B2B-App)
- **Q4 2027:** Erste Cross-App-Integration (z.B. Meeting-Notiz wird automatisch Kontakt-Notiz)
- **2028:** Drittes Produkt im Stack

Detail-Dokumentation in `docs/PLATFORM.md`.

---

## 12. Architecture Decision Records

Wichtige Architektur-Entscheidungen werden als ADRs in `docs/adrs/` festgehalten:

- **ADR-001:** Olares-native statt Supabase-Stack (Status: Accepted)
- **ADR-002:** Qwen 2.5 14B statt Llama 3.1 als Default-LLM
- **ADR-003:** PWA statt Native App
- **ADR-004:** Multi-Box-Pattern statt Cloud-Sync
- **ADR-005:** MinIO statt /app/data für Audio (Status: Proposed)
- **ADR-006:** WebSocket statt NATS für Realtime-Updates an Frontend
