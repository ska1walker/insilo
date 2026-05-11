# Architektur

> System-Architektur für insilo. Datenfluss, Komponenten, Deployment-Topologie.

---

## 1. Topologie auf hohem Niveau

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BEIM KUNDEN (on-prem)                        │
│                                                                     │
│   ┌──────────────┐         ┌──────────────────────────────────┐    │
│   │ Mitarbeiter  │  HTTPS  │         Olares-Box                │    │
│   │ Smartphone   │ ──────→ │   ┌──────────────────────────┐   │    │
│   │ (PWA)        │         │   │  Ingress / TLS (Olares)  │   │    │
│   └──────────────┘         │   └────────────┬─────────────┘   │    │
│                            │                ↓                  │    │
│                            │   ┌──────────────────────────┐   │    │
│                            │   │  Next.js (PWA-Server)    │   │    │
│                            │   └────────────┬─────────────┘   │    │
│                            │                ↓                  │    │
│                            │   ┌──────────────────────────┐   │    │
│                            │   │  FastAPI Backend         │   │    │
│                            │   │  /api/v1/*               │   │    │
│                            │   └────┬────┬────┬───────────┘   │    │
│                            │        │    │    │                │    │
│                            │        ↓    ↓    ↓                │    │
│                            │   ┌──────┐ ┌──────┐ ┌────────┐   │    │
│                            │   │Super │ │Redis │ │Celery  │   │    │
│                            │   │base  │ │      │ │Workers │   │    │
│                            │   └──────┘ └──────┘ └────┬───┘   │    │
│                            │                          │       │    │
│                            │        ┌─────────────────┘       │    │
│                            │        ↓                          │    │
│                            │   ┌──────────────────────────┐   │    │
│                            │   │  AI Services             │   │    │
│                            │   │  ├─ faster-whisper       │   │    │
│                            │   │  ├─ Ollama (Qwen 2.5)    │   │    │
│                            │   │  └─ BGE-M3 (Embeddings)  │   │    │
│                            │   └──────────────────────────┘   │    │
│                            └──────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

       ╳ KEIN Outbound zu Cloud-Diensten ╳
       (außer optional: Update-Pull-Mechanismus, vom Kunden steuerbar)


┌─────────────────────────────────────────────────────────────────────┐
│              kaivo.studio Geschäftsinfrastruktur                    │
│              (strikt getrennt von Kundendaten)                      │
│                                                                     │
│   Vercel:    Marketing-Website, Update-Repo, Lizenzverwaltung      │
│   Supabase:  CRM, Vertragsdaten, eigene Buchhaltung                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Datenfluss: Vom Mikrofon zur Notiz

```
1. AUFNAHME
   ────────
   PWA nutzt MediaRecorder API
   Format: WebM/Opus, Mono, 16 kHz Sample Rate
   Chunking: 30s-Chunks für Resilienz bei Verbindungsabbruch
   Lokales Caching in IndexedDB bis erfolgreicher Upload

2. UPLOAD
   ──────
   PWA → POST /api/v1/recordings/upload (Chunk-für-Chunk, resumable)
   Validierung: User-Auth, Größenlimit, Audio-Mime-Type
   Speicherung: Supabase Storage Bucket "audio"
   Erzeugt: meetings.id (UUID), meetings.status = "uploading"

3. JOB-DISPATCH
   ────────────
   Nach erfolgreichem Upload: Celery-Task "transcribe_meeting" eingereiht
   meetings.status = "queued"
   PWA bekommt Webhook/Realtime-Update via Supabase Realtime

4. TRANSKRIPTION
   ─────────────
   Celery-Worker holt sich Audio aus Storage
   faster-whisper large-v3 läuft auf GPU
   Speaker Diarization via pyannote.audio
   Output: structured JSON
     {
       segments: [
         {start: 0.0, end: 4.2, speaker: "S1", text: "Guten Morgen..."},
         ...
       ]
     }
   Speicherung: transcripts Tabelle (JSONB)
   meetings.status = "transcribed"

5. ZUSAMMENFASSUNG
   ────────────────
   Zweiter Celery-Task "summarize_meeting" wird automatisch gestartet
   System-Prompt zieht aktives Template aus templates Tabelle
   LLM-Call an Ollama (lokal, http://ollama:11434)
   Modell: qwen2.5:14b-instruct-q4_K_M
   Strukturiertes JSON-Output gemäß Template-Schema
   Speicherung: summaries Tabelle (JSONB)

6. EMBEDDING & SUCHE
   ──────────────────
   Dritter Task "embed_meeting" startet parallel
   Chunkt Transkript in semantische Einheiten (~500 Tokens)
   BGE-M3 generiert Embeddings (1024-dim)
   Speicherung: meeting_chunks Tabelle mit pgvector-Spalte

7. UI-UPDATE
   ──────────
   PWA bekommt Realtime-Notification: "Meeting fertig"
   meetings.status = "ready"
   User kann Transkript, Zusammenfassung, "Ask" nutzen
```

---

## 3. Komponenten-Verantwortlichkeiten

### Frontend (PWA)

**Was es macht:**
- Audio-Aufnahme mit MediaRecorder API
- Lokales Audio-Caching in IndexedDB (für Offline-Aufnahme)
- Chunked Resumable Upload zur Box
- Realtime-Updates über Supabase Realtime
- Box-Profil-Verwaltung (Multi-Box-Support)
- Service Worker für Offline-Capability

**Was es NICHT macht:**
- Keine eigene Transkription (zu schwer fürs Handy)
- Kein direktes LLM-Aufrufen
- Keine Speicherung von langfristigen Daten (außer Cache)

### Backend (FastAPI)

**Was es macht:**
- Authentifizierte REST-API für die PWA
- Validierung & Autorisierung (über Supabase JWT)
- Audio-Upload-Handling
- Job-Orchestrierung (Celery)
- Webhooks/Realtime-Trigger
- Admin-Endpoints (User-Management, Template-Verwaltung)

**Was es NICHT macht:**
- Keine direkte DB-Abfrage von User-Daten (geht über Supabase Client mit RLS)
- Keine synchronen KI-Calls (alle async über Celery)

### KI-Services (containerisiert, auf der Box)

**faster-whisper** — Transkription
- Container: `python:3.11-slim` + `faster-whisper`
- Modell: `large-v3` (~3 GB)
- GPU-Zugriff über CUDA (Olares stellt das bereit)

**Ollama** — LLM
- Standard-Container von Ollama
- Modell: `qwen2.5:14b-instruct-q4_K_M`
- HTTP-API auf Port 11434
- Verbraucht ~10 GB VRAM

**BGE-M3** — Embeddings
- Container mit `sentence-transformers`
- Modell: `BAAI/bge-m3` (~2 GB)
- FastAPI-Wrapper mit `/embed`-Endpoint

### Datenbank (Self-hosted Supabase)

**Was es bereitstellt:**
- PostgreSQL 16 mit Extensions: `pgvector`, `pg_trgm`, `uuid-ossp`
- Auth (E-Mail/Passwort + Magic Link, kein OAuth)
- Storage (S3-API für Audio-Dateien)
- Realtime (WebSocket für Live-Updates an PWA)
- Row Level Security (Mandanten-Trennung)

**Datenmodell-Übersicht:**
```
orgs (Mandant pro Kunde)
 └─ users (Mitarbeiter)
     └─ user_org_roles (Rollen pro User)

meetings (eine Aufnahme)
 ├─ transcripts (1:1, JSONB Speaker-Segmente)
 ├─ summaries (1:n, mehrere Template-Outputs möglich)
 ├─ meeting_chunks (1:n, für semantische Suche mit pgvector)
 └─ meeting_tags (n:n, freie Verschlagwortung)

templates (Zusammenfassungs-Templates)
 └─ template_org_links (welcher Mandant welche Templates aktiv hat)

audit_log (jede Datenänderung)
```

Detailliertes Schema: siehe `supabase/migrations/`.

---

## 4. Multi-Tenancy

Jede Kunde-Box hat **eine** Olares-Instanz, aber kann **mehrere Mandanten (orgs)** beherbergen. Das ist wichtig für Beratungen, die mehrere Klienten betreuen, oder für Holdings mit Tochtergesellschaften.

**RLS-Regeln (Beispiele, Implementation in Migration):**

```sql
-- Meetings: User sieht nur Meetings seiner Org
CREATE POLICY meetings_select ON meetings
  FOR SELECT
  USING (
    org_id IN (
      SELECT org_id FROM user_org_roles
      WHERE user_id = auth.uid()
    )
  );

-- Templates: System-Templates für alle, Custom nur für eigene Org
CREATE POLICY templates_select ON templates
  FOR SELECT
  USING (
    is_system = true OR
    org_id IN (
      SELECT org_id FROM user_org_roles
      WHERE user_id = auth.uid()
    )
  );
```

---

## 5. Box-Onboarding (Endnutzer-Sicht)

```
Erste Inbetriebnahme:

1. Nutzer öffnet https://meeting.kanzlei-mueller.de im Browser
2. Browser zeigt PWA-Installations-Banner
3. Nutzer installiert PWA aufs Smartphone (Add to Homescreen)
4. PWA startet, zeigt Onboarding-Screen "Box verbinden"
5. Nutzer wählt eine der drei Methoden:
   a) QR-Code scannen (Box-Admin generiert QR mit URL + Einmal-Token)
   b) Server-URL manuell eingeben
   c) Aus Liste auswählen (wenn mehrere Boxen bekannt)
6. PWA testet Erreichbarkeit der Box (/health-Endpoint)
7. Nutzer loggt sich mit E-Mail + Passwort ein (Supabase Auth)
8. Magic-Link kommt per E-Mail (über Box-internen SMTP-Relay)
9. Bei Login: PWA speichert Box-Profil in IndexedDB
10. Hauptscreen wird geladen
```

**Multi-Box (Berater-Use-Case):**
```
- Header der PWA zeigt aktuelle Box-Auswahl (wie Slack-Workspaces)
- "+" zum Hinzufügen weiterer Boxen
- Jedes Box-Profil hat eigenen IndexedDB-Namespace
- Daten werden NIE zwischen Boxen geteilt
```

---

## 6. Sicherheitsarchitektur

### Verschlüsselung

- **Transport:** TLS 1.3 zwischen PWA und Box (auto-provisioniert von Olares)
- **At-Rest:** PostgreSQL mit `pgcrypto` für sensible Felder
- **Audio-Dateien:** Im Storage Bucket mit Server-Side-Encryption
- **Backup:** Optional, Kunde-konfiguriert, kein automatisches Cloud-Backup

### Authentifizierung

- Supabase Auth, lokal auf der Box
- E-Mail + Passwort als Standard
- Magic Link über lokalen SMTP-Relay (kein externes E-Mail-Provider!)
- Optional: SSO über Olares ID System
- 2FA für Admin-Accounts (TOTP)

### Audit-Log

Jede Datenänderung wird in `audit_log` festgehalten:
- Wer (user_id)
- Wann (timestamp)
- Was (action, table, record_id)
- Wo (IP, User-Agent)
- Was alt vs. neu (JSONB diff)

Nicht löschbar durch Nutzer, nur durch Org-Admin nach Aufbewahrungsfrist.

### Datenlöschung

- Soft-Delete als Default (30 Tage Wiederherstellungsfrist)
- Hard-Delete-Worker läuft nächtlich, löscht > 30 Tage alte Soft-Deletes
- DSGVO-konforme "Recht auf Vergessen"-Funktion: Admin kann sofort Hard-Delete erzwingen

Mehr in `docs/SECURITY.md`.

---

## 7. Performance-Erwartungen

| Operation                              | Erwartung (Olares One)    |
|----------------------------------------|---------------------------|
| Upload 60-Min-Meeting (50 MB)          | ~30 Sek bei LAN           |
| Transkription 60-Min-Meeting           | 4-7 Min (faster-whisper)  |
| Speaker Diarization 60-Min             | +2-3 Min                  |
| Zusammenfassung 60-Min-Transkript      | 30-60 Sek (Qwen 2.5)      |
| Embedding 60-Min-Transkript            | 10-20 Sek (BGE-M3)        |
| "Ask Plaud"-Query                      | 1-3 Sek                   |
| **Total: Aufnahme bis fertige Notiz**  | **~10 Min für 60-Min-Meeting** |

**Parallelität:**
- 2-3 gleichzeitige Aufnahmen können parallel transkribiert werden, ohne dass es spürbar langsamer wird
- Bei mehr → Queue baut sich auf, Nutzer sehen geschätzte Wartezeit

---

## 8. Offline-Fähigkeit

**Was offline funktioniert (PWA):**
- Bereits geladene Meetings anschauen (Cache)
- Neue Aufnahme starten (wird lokal gepuffert)
- Notizen lesen, manuelle Markierungen setzen

**Was offline NICHT funktioniert:**
- Neue Transkription (braucht Box-Backend)
- Suchen über Embedding-Index
- Login mit Magic Link

**Sync-Verhalten:**
- Sobald Box wieder erreichbar: gepufferte Aufnahmen werden hochgeladen
- Konflikte werden mit "Last-Write-Wins" gelöst (außer bei Notizen, wo Merge versucht wird)

---

## 9. Update-Strategie

Drei Update-Modi, vom Kunden in der Box-Admin-UI wählbar:

**Modus 1: Auto-Pull (Default für die meisten Kunden)**
- Box checkt täglich `https://updates.kaivo.studio/insilo/latest`
- Wenn neue Version: download, signature-check, installieren bei Wartungsfenster
- Outbound nur zu kaivo.studio Update-Server (kein Kundendaten-Upload)

**Modus 2: Manuelle Freigabe**
- Box meldet "Update verfügbar" in Admin-UI
- Admin entscheidet, wann installiert wird

**Modus 3: Air-Gapped**
- Keine Outbound-Verbindung
- kaivo.studio schickt signierte Update-Pakete per USB / sicherem File-Transfer
- Manuelle Installation durch Kunde-Admin

Mehr in `docs/DEPLOYMENT.md`.

---

## 10. Entscheidungsprotokoll (Architecture Decision Records)

Wichtige Architektur-Entscheidungen werden als ADRs in `docs/adrs/` festgehalten. Format:
```
ADR-001: Self-hosted Supabase statt PostgreSQL pur
- Status: Accepted
- Context: ...
- Decision: ...
- Consequences: ...
```

Aktuelle ADRs:
- ADR-001: Self-hosted Supabase (in Phase 1 anzulegen)
- ADR-002: Qwen 2.5 statt Llama 3.1 als Default-LLM (in Phase 1 anzulegen)
- ADR-003: PWA statt Native App (in Phase 1 anzulegen)
- ADR-004: Multi-Box-Pattern statt Cloud-Sync (in Phase 1 anzulegen)
