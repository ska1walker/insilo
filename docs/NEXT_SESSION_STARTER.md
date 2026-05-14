# Next-Session-Starter

Diese Datei ist der **Aufschlag-Prompt für ein frisches Kontextfenster**.
Kopiere unten alles unter „— Prompt-Anfang —" in das neue Chat-Fenster.

---

## — Prompt-Anfang —

Lies dich ein:

1. **`CLAUDE.md`** — Projekt-Briefing, Olares-Constraints, Tech-Stack.
2. **`docs/HANDOFF.md`** — Status + Learnings. **Besonders der Header
   oben ($1) sowie §7g „v0.1.14 → v0.1.16 Lessons".**

**Stand:** Insilo läuft als **v0.1.36** auf der Olares-Box
`olares@192.168.112.125` (Olares-User `kaivostudio`,
Box-URL `https://e5d605f3.kaivostudio.olares.de`). Alle 5 Pods Ready.
Feature-Set komplett: Aufnahme + Diarization + Transkript + Summary +
Q&A + Templates + Speaker-Editing + Tags + Filter + **Outbound-Webhooks
+ externe REST-API + Markdown-Export**.

**Was in v0.1.35/v0.1.36 dazukam:** Migration 0005 (`org_webhooks`,
`webhook_deliveries`, `api_keys`), Celery-Dispatcher mit Fan-Out + Retry
(`backend/app/tasks/notify.py`), Markdown-Renderer
(`backend/app/exports/markdown.py`), REST-API `/api/external/v1/*` mit
Bearer-Token, UI-Sektionen in `/einstellungen` (Webhook-Manager + API-Key-
Manager + ContractDisclosure-Hilfe), Doku `docs/WEBHOOKS.md`.

**Nächste geplante Iteration: Duo-Empfänger-Endpoint in Duo
(duo.aimighty.de) bauen.** Insilo-Seite ist fertig — Integration läuft
nur noch als Konfiguration.

Die Vision (vom User):
> Insilo schreibt nach jeder Transkription Meeting-Minutes als Markdown
> nach Duo (Cloud-Knowledge-Hub). OpenWebUI greift auf Duo zu und
> beantwortet Fragen wie „Sind noch Aufgaben offen?", „Mach einen
> One-Pager zur Sitzung von letzter Woche". Aufgaben aus Insilo-Meetings
> landen als Checklist-Items in Duo → über alle Meetings aggregierbar.

**Was wir bereits wissen (Stand v0.1.36):**

- **Duo ist eine Cloud-App des Users** (`duo.aimighty.de`). Notizen +
  Folders + Tasks, Multi-User. User baut Duo selbst und kann
  Webhook-Empfänger einbauen.
- **Empfohlene Integration:** Webhook-Push von Insilo nach Duo,
  HMAC-Signatur. Insilo-Seite ist **fertig** — fehlt nur der Empfänger
  in Duo. Voller Vertrag in `docs/WEBHOOKS.md`.

**Erste Aufgabe in der nächsten Session:**

1. Mit User abklären, welcher Stack in Duo läuft (Node/Python/Go?).
2. Empfänger-Endpoint `POST /api/integrations/insilo` in Duo bauen:
   - HMAC-SHA256-Verify mit `hmac.compare_digest`
   - Idempotenz via `X-Insilo-Delivery-ID` (Tabelle
     `processed_webhook_deliveries`)
   - Upsert `notes` über `(external_source='insilo', external_id=meeting.id)`
3. Optional: Checkbox-Parser für `## Offene Aufgaben` → Duo-Tasks.
4. End-to-End-Test gegen die Box.

**Architektur-Skizze (in HANDOFF.md Header detaillierter):**

```
Meeting fertig (status="ready")
        ↓
1. Webhook-POST an konfigurierbare URL(s)
        ↓
2. File-Export-Adapter schreibt Markdown nach
   hostPath /app/data/exports/<duo-pfad>/
        ↓
3. Duo bemerkt neuen .md → indexiert → OpenWebUI weiß Bescheid
```

**Markdown-Template-Vorschlag:**

```markdown
---
source: insilo
meeting_id: <uuid>
title: <Title>
date: <ISO-Date>
duration_min: <number>
speakers: [<Name>, <Name>]
tags: [<tag>, <tag>]
template: <Template-Name>
---

# <Title> — <Date>

## Zusammenfassung
…

## Beschlüsse
- …

## Offene Aufgaben
- [ ] <Was> (<Wer>, bis <Wann>)

## Volltranskript
[mm:ss] <Sprecher>: <Text>
```

**Bauteile, die wir wahrscheinlich brauchen:**

| Komponente | Wo | Zweck |
|---|---|---|
| Webhook-Endpoint-Konfig | `org_settings`-Tabelle erweitern | Per-Org Webhook-URL(s) |
| Webhook-Dispatcher | `app/tasks/notify.py` (NEU) | Celery-Task: POST nach status=ready |
| File-Export-Adapter | `app/exports/markdown.py` (NEU) | Markdown rendern + schreiben |
| Export-Pfad-Konfig | `org_settings` erweitern | hostPath für Duo-Ordner |
| Trigger im Worker | `app/tasks/summarize.py` Ende | nach DB-Update → notify-Task |
| API-Keys + Verwaltung | neue Tabelle `api_keys` + UI in `/einstellungen` | REST-API authentifizieren |
| REST-API für Pull | `app/routers/api.py` (NEU) | GET /api/v1/external/meetings mit Token |

**Bevor du Code schreibst:** stelle die 4 Fragen oben, dann lies
`docs/HANDOFF.md` $1 (Header-Banner) komplett. Erst dann planen.

**Tools im Repo, die du nutzt:**
- **Release-Script:** `bash scripts/release.sh 0.1.35 --yes -m "..."`
  bumpt Versionen, lint, package, commit, tag, push, copy to ~/Downloads.
- **Migrations-Generator:** `python3 scripts/regen-migrations.py` —
  pflichtmäßig nach Schema-Änderung.
- **Chart-Checks:** `bash scripts/check-chart.sh` — läuft auch in CI.

**SSH-Zugang zur Box:**
```bash
ssh olares@192.168.112.125
# Helm braucht: KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

Volle Pipeline für Box-Update:
```bash
scp dist/insilo-0.1.X.tgz olares@192.168.112.125:/tmp/
ssh olares@192.168.112.125 \
  'KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm upgrade insilo \
    /tmp/insilo-0.1.X.tgz -n insilo-kaivostudio --reuse-values \
    --set images.frontend.tag=0.1.X \
    --set images.backend.tag=0.1.X \
    --set images.whisper.tag=0.1.X \
    --set images.embeddings.tag=0.1.X'
```

— Prompt-Ende —

---

## Status-Quick-Reference

| Bereich | Stand |
|---|---|
| Version | v0.1.36 (alle 5 Pods Ready) |
| Plattform | Olares OS (k3s) auf `192.168.112.125` |
| Box-User | `kaivostudio` |
| URL | `https://e5d605f3.kaivostudio.olares.de` |
| Container | `ghcr.io/ska1walker/insilo-{frontend,backend,whisper,embeddings}:0.1.36` |
| LLM | Per-Org konfigurierbar via `/einstellungen` (Default Olares-LiteLLM) |
| Diarization | Lokal, token-frei (Silero-VAD + SpeechBrain ECAPA + sklearn) |
| Storage | hostPath `/app/data/audio/` für Audio, Postgres für Rest |

## Offene Issues / Bekannte Stolpersteine

- **Online-Builds dauern** ~6-9 min weil Whisper-Image ~1.2 GB (torch + speechbrain). Akzeptabel.
- **GHCR-Login kann timeout** machen (transient). Re-run der failed jobs reicht meist (`gh run rerun <id> --failed`).
- **Service-Worker-Cache** im Browser: nach jedem Frontend-Deploy einmal Cmd-Shift-R, sonst sieht User alte Version.

## Wichtige Dateien zum Lesen vor dem ersten Commit

1. `CLAUDE.md` — Briefing
2. `docs/HANDOFF.md` — Status + Lessons
3. `docs/DESIGN.md` — Designsystem (Weiß/Schwarz/Gold, Sie-Form, etc.)
4. `olares/OlaresManifest.yaml` — Plattform-Spec
5. `scripts/check-chart.sh` — die 9 Phase-4-Lessons als Code

## Letzter Commit + GH State (zum Stand dieses Handoffs)

```bash
git log --oneline -5
gh run list --workflow=release.yml --limit 3
```

Sollte v0.1.34 als jüngsten Tag zeigen, falls v0.1.35 noch nicht
gestartet wurde.
