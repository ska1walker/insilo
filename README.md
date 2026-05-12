# Insilo

> Datensouveräne Meeting-Intelligenz für deutschen Mittelstand.
> Läuft komplett auf einer Olares-Box im Serverraum des Kunden.
>
> **Maintainer:** Kai Böhm ([kaivo.studio](https://kaivo.studio))
> **Vertrieb:** [aimighty.de](https://aimighty.de)
> **Status:** Phase 1 — MVP-Setup

---

## Was Insilo ist

Insilo nimmt Geschäftsbesprechungen auf, transkribiert sie lokal mit Whisper und erstellt strukturierte Notizen mit einem lokal laufenden Sprachmodell.

**Kernversprechen:** Keine einzige Audiosekunde, kein Transkript, kein Suchindex verlässt jemals die Olares-Box des Kunden.

Geeignet für: Anwaltskanzleien, Steuerberatungen, Beratungen, Industriebetriebe mit Compliance-Anforderungen.

**Im Unterschied zu PLAUD, Otter, Fireflies:** Keine US-Cloud-AI, keine externen API-Calls. Alles on-prem.

---

## Architektur in einer Minute

- **Plattform:** Olares OS (Kubernetes-basiert) beim Kunden
- **Frontend:** Next.js 15 PWA — Smartphone wird zum Mikrofon
- **Backend:** FastAPI (Python)
- **Transkription:** faster-whisper large-v3 mit Speaker Diarization (pyannote)
- **LLM:** Ollama mit Qwen 2.5 14B (Quant Q4_K_M)
- **Embeddings:** BGE-M3 für semantische Suche
- **Datenbank:** Olares-System-PostgreSQL + pgvector
- **Cache/Queue:** Olares-System-KVRocks (Redis-API-kompatibel)
- **Auth:** Olares-System (Authelia + Envoy-Sidecar — wir implementieren nichts selbst)

Details in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

---

## Verzeichnisstruktur

```
insilo/
├── CLAUDE.md                     # Briefing für Claude Code
├── README.md                     # diese Datei
├── QUICKSTART.md                 # lokales Setup für Entwickler
├── docker-compose.yml            # lokale Dev-Umgebung
├── .env.example
│
├── docs/                         # Konzept- und Designdokumente
│   ├── ARCHITECTURE.md
│   ├── DESIGN.md
│   ├── ROADMAP.md
│   ├── SECURITY.md
│   ├── DEPLOYMENT.md
│   └── PLATFORM.md               # langfristige Multi-App-Vision
│
├── frontend/                     # Next.js 15 PWA
├── backend/                      # FastAPI
├── supabase/migrations/          # SQL-Migrationen für Olares-PostgreSQL
└── olares/                       # Helm-Chart für Olares-Markt
```

---

## Schnellstart

```bash
git clone git@github.com:ska1walker/insilo.git
cd insilo
cp .env.example .env
docker-compose up -d
cd frontend && npm install && npm run dev
```

Details in [`QUICKSTART.md`](./QUICKSTART.md).

---

## Roadmap (Kurzform)

- **Phase 1** (jetzt) — Setup, Schema, Aufnahme, Whisper-Transkription
- **Phase 2** — LLM-Zusammenfassungen, Speaker Diarization, Templates
- **Phase 3** — "Ask"-Funktion (RAG), Live-Transkription
- **Phase 4** — Olares-Paketierung & Markt-Upload
- **Phase 5** — Pilot-Deployment bei ersten Kunden
- **Phase 6** — Skalierung & Plattform-Erweiterung

Details in [`docs/ROADMAP.md`](./docs/ROADMAP.md).

---

## Lizenz

Proprietär. © 2026 Kai Böhm / kaivo.studio. Alle Rechte vorbehalten.

---

## Kontakt

- **Entwicklung:** kai@kaivo.studio
- **Vertrieb:** kontakt@aimighty.de
- **Sicherheit:** security@kaivo.studio
