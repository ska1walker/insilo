# insilo

> Datensouveräne Meeting-Intelligenz für den deutschen Mittelstand.

Eine On-Premise-Lösung, die Geschäftsgespräche aufnimmt, transkribiert und zu strukturierten Notizen zusammenfasst — vollständig auf der Hardware des Kunden, ohne dass Daten das Firmennetzwerk verlassen.

## Komponenten

| Komponente   | Rolle                                                          |
|--------------|----------------------------------------------------------------|
| **PWA**      | Smartphone-App des Endnutzers. Aufnahme, Anzeige, Suche.       |
| **Backend**  | FastAPI-Service auf der Olares-Box. Orchestriert KI-Modelle.   |
| **KI-Stack** | Whisper (STT) + Qwen 2.5 (LLM) + BGE-M3 (Embeddings) lokal.    |
| **Daten**    | Self-hosted Supabase auf der Box.                              |
| **Hardware** | Olares One (vorkonfiguriert vom Hersteller).                   |

## Quick Links

- [Architektur](./docs/ARCHITECTURE.md)
- [Design-System](./docs/DESIGN.md)
- [Roadmap](./docs/ROADMAP.md)
- [Sicherheit](./docs/SECURITY.md)
- [Deployment](./docs/DEPLOYMENT.md)

## Wie es funktioniert

```
┌─────────────────┐         ┌──────────────────────────────┐
│   Smartphone    │         │  Olares-Box (beim Kunden)    │
│   (PWA, Browser)│         │                              │
│                 │  HTTPS  │  ┌────────────────────────┐  │
│  Aufnahme  ────────────────→ │  FastAPI               │  │
│  Liste     ←─────────────── │  Whisper · Ollama · BGE│  │
│  Detail    ←─────────────── │  Supabase (DB + Auth)  │  │
│                 │         │  └────────────────────────┘  │
└─────────────────┘         └──────────────────────────────┘
                                         │
                                    (offline möglich)
```

## Status

Phase 1 — MVP-Setup. Siehe [ROADMAP.md](./docs/ROADMAP.md).

## Lizenz

Proprietär. © kaivo.studio.
