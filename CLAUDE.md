# insilo — Projekt-Briefing für Claude Code

> **Markenname:** insilo
> **Maintainer:** Kai Böhm (kaivo.studio)
> **Vertrieb:** über aimighty.de
> **Status:** Phase 1 — MVP-Setup
> **Letzte Aktualisierung:** Mai 2026

---

## Was wir bauen

Eine **datensouveräne, on-premise Meeting-Intelligenz-Lösung für den deutschen Mittelstand**.

Das Produkt besteht aus drei zusammengehörigen Teilen:

1. **PWA (Frontend)** — installiert sich aus dem Browser auf dem Smartphone des Endnutzers. Nimmt Audio auf, zeigt Transkripte, Zusammenfassungen, ermöglicht "Ask"-Funktion auf Meeting-Archiv.
2. **Backend-API** — läuft auf einer Olares-Box im Serverraum des Kunden. Orchestriert Whisper (Transkription), Qwen 2.5 14B via Ollama (LLM), BGE-M3 (Embeddings), Supabase (Daten + Auth + Storage).
3. **Olares-App-Paket** — paketiert das Gesamtsystem so, dass der Kunde es mit einem Klick auf seiner Box installieren kann.

**Kernversprechen:** Keine einzige Audiosekunde, kein Transkript, kein Suchindex verlässt jemals die Olares-Box des Kunden. Verkaufsargument gegen PLAUD, Otter, Fireflies und alle Cloud-Konkurrenten.

**Zielsegment:** Kanzleien, Steuerberatungen, Beratungen, Industrie-Mittelstand mit Compliance-Druck (DSGVO, Betriebsrat, Schweigepflicht).

---

## Multi-Box-Architektur

**Wichtigste Architektur-Eigenheit:** Die PWA wird *einmal* gebaut, aber an viele Kunden verteilt. Jeder Kunde hat seine eigene Olares-Box. Im Onboarding gibt der Nutzer die **Server-URL seiner Box** in die PWA ein.

```
PWA (eine Codebase, ausgeliefert über aimighty oder direkt)
   │
   ├──→ Box Kunde A (kanzlei-mueller.local)
   ├──→ Box Kunde B (steuer-schmidt.local)
   └──→ Box Kunde C (industrie-weber.local)
```

Die PWA ist also **box-agnostisch**. Alle Daten (Auth-Tokens, gecachte Meetings, Konfiguration) werden im IndexedDB des Browsers gespeichert, pro Box separiert. Multi-Box-Support (für Berater, die mehrere Kunden betreuen) muss von Anfang an mitgedacht sein — Slack-Workspace-Pattern.

---

## Tech-Stack

### Frontend (PWA)
- **Framework:** Next.js 15 (App Router, RSC wo möglich)
- **Sprache:** TypeScript (strict mode)
- **Styling:** Tailwind CSS v4 + shadcn/ui (HubSpot-stylisiert)
- **Icons:** Lucide React
- **State:** Zustand (lokal) + TanStack Query (Server-State)
- **Audio:** MediaRecorder API + WebRTC für Live-Streaming
- **Offline:** Service Worker mit Workbox, IndexedDB für lokales Caching
- **PWA-Manifest:** standard, mit "Installable" Icons

### Backend (auf der Olares-Box)
- **API:** FastAPI (Python 3.11+)
- **Datenbank:** Self-hosted Supabase (PostgreSQL + pgvector + Auth + Storage + Realtime)
- **Transkription:** faster-whisper mit `large-v3` Modell
- **Speaker Diarization:** pyannote.audio (über WhisperX)
- **LLM-Runtime:** Ollama
- **LLM-Modell:** Qwen 2.5 14B Instruct (Q4_K_M quantisiert, ~9-10 GB VRAM)
- **Embeddings:** BGE-M3 (multilingual, Apache 2.0)
- **Object Storage:** Supabase Storage (S3-kompatibel, auf der Box)
- **Background-Jobs:** Celery + Redis (für lange Whisper/LLM-Tasks)

### Infrastruktur (Olares-Spezifika)
- **Orchestrierung:** Kubernetes via Olares OS (kommt out-of-the-box)
- **Reverse Proxy:** Built-in Olares Ingress
- **TLS:** Auto-Provisioning über Olares ID System
- **Remote-Support:** Tailscale (in Olares integriert)
- **Updates:** Pull-Modell als Default, Air-Gapped als Premium-Option

### Eigene Geschäftsinfrastruktur (kaivo.studio, NICHT auf Kundenboxen)
- Vercel-gehostete Website / Update-Repository / Lizenz-Verwaltung
- Strikt getrennt von Kundendaten

---

## Verzeichnisstruktur

```
insilo/
├── CLAUDE.md                    # dieses Dokument
├── README.md                    # öffentliche Projektbeschreibung
├── docs/
│   ├── ARCHITECTURE.md          # Datenfluss, Komponenten, Diagramme
│   ├── DESIGN.md                # Design-System (Farben, Typo, Komponenten)
│   ├── ROADMAP.md               # Phasen, Milestones
│   ├── SECURITY.md              # Datenschutz-Versprechen, Audit-Punkte
│   └── DEPLOYMENT.md            # Olares-App-Paketierung, Updates
├── frontend/                    # Next.js 15 PWA
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── public/
├── backend/                     # FastAPI auf der Box
│   ├── app/
│   │   ├── api/
│   │   ├── services/            # whisper, llm, embeddings
│   │   ├── models/              # Pydantic
│   │   └── workers/             # Celery Tasks
│   ├── tests/
│   └── pyproject.toml
├── supabase/                    # Datenbank-Schema
│   ├── migrations/
│   └── seed.sql
└── olares/                      # Olares-App-Manifest
    ├── OlaresManifest.yaml
    └── README.md
```

---

## Designsystem (Kurzfassung — Vollversion in `docs/DESIGN.md`)

**Drei Anker:**
- **HubSpot Canvas** → Komponenten-Sprache, Spacing, Klarheit
- **aimighty.de** → Farbwelt (Weiß / Schwarz / Gold)
- **PLAUD App** → App-Architektur, Übersichtlichkeit, Screen-Aufbau

**Informationsdichte-Strategie:** PLAUD-reduzierte Hauptscreens, HubSpot-dichte Detailviews.

**Farben:** `#FFFFFF` (weiß), `#0A0A0A` (schwarz), `#C9A961` (Gold-Akzent, sehr sparsam).

**Typografie:** Lexend Deca (Display) + Inter (Body) + JetBrains Mono (Timestamps/Speaker).

**Anti-Patterns:** Keine Gradients, keine Glassmorphism, kein Lila, keine fetten Marketing-Headlines, kein Card-in-Card, keine AI-Sparkles.

**Identitäts-Kante:** Goldene 1px-Linie am oberen Bildschirmrand pulsiert während aktiver Aufnahme. *Die* visuelle Signatur.

**Aktivierte Claude-Code-Skills:**
- `frontend-design` (Anthropic offiziell)
- `UI/UX Pro Max` (Community-Skill von nextlevelbuilder)

**Wichtig für Claude Code:** Wir folgen den HubSpot/PLAUD-Design-Vorgaben *konkret*, auch wenn der `frontend-design` Skill generell zu "distinctiveren" Fonts rät. Lexend + Inter sind hier eine bewusste, kontextspezifische Entscheidung.

---

## Schreibstil & Sprache

- **Kunden-UI:** Sie-Form, formelles Deutsch, "Freundliche Grüße"-Tonalität
- **Microcopy:** sachlich, präzise, ohne Marketing-Sprech
- **Fehlermeldungen:** menschlich, lösungsorientiert ("Die Verbindung zur Box scheint unterbrochen. Bitte prüfen Sie die Server-URL in den Einstellungen.")
- **Keine Anglizismen wo deutsches Wort existiert** ("Meeting" → "Besprechung" wo passend; "Recording" → "Aufnahme")
- **Code-Kommentare und commit messages:** Englisch (Standard)
- **User-facing docs:** Deutsch
- **Diese CLAUDE.md, ARCHITECTURE.md, etc.:** Deutsch (Arbeitssprache des Maintainers)

---

## Kernprinzipien (für jede Code-Entscheidung)

1. **Datensouveränität ist nicht verhandelbar.** Jede Funktion, die Kundendaten ins Internet schicken würde, wird nicht gebaut. Keine Telemetrie. Kein "Phone Home". Keine externen Schriften, die nicht self-hosted sind (Google Fonts in Production → self-host nach Build).

2. **Box-Agnostik.** Die PWA darf *keine* hartcodierten URLs enthalten. Alles über User-konfigurierte Box-Profile.

3. **Multi-Tenant von Anfang an.** Mehrere Mitarbeiter eines Kunden teilen sich eine Box. Row-Level Security in Supabase ist Pflicht, nicht Option.

4. **Offline-First wo möglich.** PWA muss Meetings im Browser-Cache anzeigen können, auch wenn die Box gerade nicht erreichbar ist. Aufnahmen können offline gestartet und später hochgeladen werden.

5. **Audit-Trail.** Jede Datenänderung wird geloggt (wer, wann, was). Compliance-relevant für Anwälte und Steuerberater.

6. **Reversibilität.** Vor jedem destruktiven Vorgang: Soft-Delete mit 30-Tage-Frist. Erst danach Hard-Delete.

7. **Performance ist UX.** Whisper-Transkription darf nicht das UI blockieren. Background-Jobs + Progress-Indicators sind Pflicht.

8. **Keep it boring.** Stack-Entscheidungen folgen erprobten Pfaden (Next.js, FastAPI, Supabase). Keine bleeding-edge-Experimente.

---

## Phasenplan (Detail in `docs/ROADMAP.md`)

- **Phase 1 (jetzt):** Setup, Schema, Auth, Box-Onboarding, einfache Aufnahme + Whisper-Transkription
- **Phase 2:** LLM-Zusammenfassungen, Speaker Diarization, Template-System
- **Phase 3:** "Ask"-Funktion (semantische Suche über Embeddings), Live-Transkription
- **Phase 4:** Olares-App-Paketierung, Pilot-Deployment beim Erstkunden
- **Phase 5:** Multi-Tenant-Features, Admin-Dashboard, Audit-Log-Viewer

---

## Wie Claude Code in diesem Repo arbeiten soll

1. **Bevor du Code anfasst:** Lies `docs/ARCHITECTURE.md` und `docs/DESIGN.md` in voller Länge.
2. **Bei UI-Arbeit:** Aktiviere die Skills `frontend-design` und `UI/UX Pro Max`.
3. **Folge dem Designsystem strikt.** Keine eigenen Farb- oder Schrift-Erfindungen. Tokens aus `docs/DESIGN.md`.
4. **Bei Datenmodell-Änderungen:** Erst Migration in `supabase/migrations/` schreiben, dann Frontend/Backend anpassen.
5. **Sprachregel:** UI-Texte auf Deutsch (Sie-Form). Code auf Englisch. Kommentare nach Bedarf.
6. **Tests:** Vitest fürs Frontend, pytest fürs Backend. Kein Code-Merge ohne Tests bei kritischen Pfaden (Auth, Audio-Upload, Transkription).
7. **Bei Unsicherheit über Architektur-Entscheidungen:** stoppen und Kai fragen. Lieber einmal zu viel rückversichern.

---

## Was NICHT gebaut wird (bewusste Nicht-Entscheidungen)

- **Eigene Mikrofon-Hardware** — wird durch Smartphone ersetzt (Differenzierung zu PLAUD)
- **Mobile Native Apps (iOS/Android)** — PWA reicht, spart App-Store-Hürden
- **Cloud-Sync zwischen Boxen** — würde Kernversprechen brechen
- **Externe AI-API-Fallbacks** — kein "wenn lokales LLM überlastet, dann OpenAI"
- **Eigene Sprachsynthese / TTS** — out of scope für MVP
- **Analytics & Tracking** — nicht auf Kundenboxen, nirgends
- **Marketplace für Templates** — ggf. Phase 5+

---

## Kontakt / Ownership

- **Product & Code:** Kai Böhm (kaivo.studio)
- **Vertrieb:** aimighty.de
- **Hosting:** Kundenseitig (Olares-Box)
- **Eigene Infrastruktur (Update-Repo, Lizenzen):** Vercel + Supabase EU (kaivo.studio)
