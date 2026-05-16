# Next-Session-Starter

Diese Datei ist der **Aufschlag-Prompt für ein frisches Kontextfenster**.
Kopiere unten alles unter „— Prompt-Anfang —" in das neue Chat-Fenster.

---

## — Prompt-Anfang —

Lies dich ein:

1. **`CLAUDE.md`** — Projekt-Briefing, Olares-Constraints, Tech-Stack.
2. **`docs/HANDOFF.md`** — Status + Learnings. **Besonders der Header
   oben ($1) sowie §7g „v0.1.14 → v0.1.16 Lessons".**

**Stand:** Insilo läuft als **v0.1.49** im Repo. v0.1.48 ist auf der Box
deployed (Helm-Rev 34, Migration 0013 erfolgreich). v0.1.49-Deploy steht
noch aus. Olares-Box: `olares@192.168.112.125` (Olares-User `kaivostudio`,
Box-URL `https://e5d605f3.kaivostudio.olares.de`). Feature-Set:

- Aufnahme + Speaker-Diarization + Transkript + Summary + Q&A + Tags
- **Outbound-Integration:** Webhooks (HMAC, Fan-Out, exp. Backoff),
  REST-API (Bearer-Token), Markdown-Export, **manueller Dispatch
  per Default**
- **Org-Sprecher-Katalog** mit Voiceprint-Matching (ECAPA-TDNN 192-d,
  Cosine ≥ 0.5, max. 20 Samples FIFO)
- **Dedizierte Stimmprobe** (Nordwind-Text) — **wieder funktional
  für WebM/Opus seit v0.1.44** (decode_audio statt sf.read)
- **Werks-Templates** komplett anpassbar: Name/Description-Override,
  System-Prompt-Override, Custom-Fields (Lite-Schema-Editor v0.1.41)
- **Meeting-Titel inline editierbar**, **Markdown-Export per Webhook**
- **Qwen 2.5-tuned LLM-Prompts** mit Few-Shot, `_analyse`-CoT-Feld,
  Eval-Baseline (12 Fixtures + 39 Snapshot-Tests)
- **i18n end-to-end (v0.1.46)** — 5 Sprachen wählbar (DE/EN/FR/ES/IT)
  in `/einstellungen`, 511 Keys pro Sprache, LLM-Prompts pro Locale
  in `templates.system_prompts JSONB` (Migration 0012),
  `summarize.py` resolved User-Locale und gibt sie dem LLM mit. UI-
  Locale-Override aus dem Cookie schickt auch `Accept-Language` an
  Backend-Calls, Backend-Errors decken alle 5 Sprachen. Schema-Keys
  bleiben deutsch (LLM-Output sprachenunabhängig), Display-Labels
  kommen über die neue `summaryLabels`-Namespace.
- **About-Page-Refresh (v0.1.47)** — `/ueber` mit Mock-Product-Hero
  (Transkript-Snippet + Pulse-Linie + Mini-Summary rechts), eigener
  Sprecher-Erkennungs-Sektion (Mock-Cluster-Liste mit 92 %-Match),
  Architektur-Diagramm (Browser→Box-API→Whisper→PostgreSQL+LLM-Branch)
  + Compliance-Bullets in der Sicherheits-Sektion. 550 Keys × 5
  Sprachen jetzt (+38 neu).
- **Audio-i18n + Legacy-Cleanup (v0.1.48)** — Whisper-Sprach-Dropdown
  in `RecordingBlock` (Auto-Detect Default + DE/EN/FR/ES/IT),
  Backend pipet `language` vom Form-Field via `meetings.language` zu
  faster-whisper durch (NULL → auto-detect). `voice-enrollment-dialog`
  zieht den North-Wind-Standardtext jetzt pro UI-Locale aus
  `voiceEnrollment.nordwindBody`. **Migration 0013** droppt
  `templates.system_prompt`, `template_customizations.system_prompt`
  und den `meetings.language`-Default; Backend-Resolver, Pydantic-
  Models, seed.sql und Frontend-DTO komplett bereinigt.
- **Audio-Quality-Sweep (v0.1.49)** — neuer Helper
  [frontend/lib/audio.ts](frontend/lib/audio.ts) zentralisiert
  `getUserMedia`-Constraints und MediaRecorder-Bitrate. Browser-DSP
  hart auf ASR-Posture umgestellt (AGC/NoiseSuppression aus,
  EchoCancellation an), 128 kbps Opus, 48 kHz mono. Whisper auf
  `beam_size=5` (war 1, „dev-speed default"). Dateien jetzt ~1 MB/min
  statt ~250 kB/min, deutsche Frikative gehen nicht mehr verloren.

**Nächste geplante Iteration: Duo-Integration (Webhook-Empfänger)**

Insilo-Seite ist seit v0.1.39 fertig: Webhook-Manager mit HMAC,
Fan-Out, Backoff, REST-API + Markdown-Export. Fehlt nur noch der
Empfänger in `duo.aimighty.de`.

Die Vision (vom User):
> Insilo schreibt nach jeder Transkription Meeting-Minutes als Markdown
> nach Duo (Cloud-Knowledge-Hub). OpenWebUI greift auf Duo zu und
> beantwortet Fragen wie „Sind noch Aufgaben offen?", „Mach einen
> One-Pager zur Sitzung von letzter Woche". Aufgaben aus Insilo-Meetings
> landen als Checklist-Items in Duo → über alle Meetings aggregierbar.

**Was wir bereits wissen:**

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
4. End-to-End-Test gegen die Box: in Insilo Meeting aufnehmen → auf
   Meeting-Detail „An externe Systeme senden" klicken → Webhook
   landet bei Duo.

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
- **Release-Script:** `bash scripts/release.sh 0.1.X --yes -m "..."`
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
| Version | **v0.1.49** (Repo; Box läuft v0.1.48, Helm-Rev 34) |
| Plattform | Olares OS (k3s) auf `192.168.112.125` |
| Box-User | `kaivostudio` |
| URL | `https://e5d605f3.kaivostudio.olares.de` |
| Container | `ghcr.io/ska1walker/insilo-{frontend,backend,whisper,embeddings}:0.1.49` |
| LLM | Per-Org konfigurierbar via `/einstellungen` (Default Olares-LiteLLM); Qwen2.5-tuned Prompts mit Few-Shot, 5-Sprachen-Prompts (v0.1.46) |
| Diarization | Lokal, token-frei (Silero-VAD + SpeechBrain ECAPA + sklearn), WebM-fähig seit v0.1.44 |
| Sprecher-Katalog | pgvector(192)+HNSW, Cosine ≥ 0.5, FIFO-Mittelwert über 20 Samples |
| Stimmprobe | „North Wind"-Fabel pro Sprache (v0.1.48), Whisper `/embed-only`-Endpoint |
| Whisper-Sprache | Per-Meeting wählbar via Dropdown (v0.1.48); NULL in `meetings.language` → faster-whisper auto-detect |
| UI-i18n | 551 Keys × 5 Sprachen, alle UI-Strings + LLM-Output-Labels lokalisiert (`summaryLabels`-Namespace) |
| Backend-i18n | `app/errors.py` mit allen 5 Sprachen; ContextVar-Resolution via Accept-Language + `insilo-locale`-Cookie aus `api/client.ts` |
| Prompts | `templates.system_prompts JSONB` (Migration 0012) — Legacy TEXT-Spalte gedroppt in 0013 (v0.1.48); Resolver pro Locale mit DE-Fallback |
| Webhooks | Auslöser pro Webhook: `manual` (Default, sicher) oder `auto` |
| i18n | next-intl@4, 5 Sprachen (DE/EN/FR/ES/IT), Locale in `/einstellungen` umschaltbar |
| Storage | hostPath `/app/data/audio/` für Audio, Postgres für Rest |
| Migrationen | 13 im Repo (0001–0013); nach Deploy auch auf der Box |

## Offene Issues / Bekannte Stolpersteine

- **Online-Builds dauern** ~6-9 min weil Whisper-Image ~1.2 GB (torch + speechbrain). Akzeptabel.
- **GHCR-Login kann timeout** machen (transient). Re-run der failed jobs reicht meist (`gh run rerun <id> --failed`).
- **Service-Worker-Cache** im Browser: nach jedem Frontend-Deploy einmal Cmd-Shift-R, sonst sieht User alte Version.

## Wichtige Dateien zum Lesen vor dem ersten Commit

1. `CLAUDE.md` — Briefing (insbes. neue Sprachregel)
2. `docs/HANDOFF.md` — Status + Lessons (v0.1.44-Block oben für Decoder-Lesson)
3. `docs/DESIGN.md` — Designsystem (Weiß/Schwarz/Gold, formelle Anrede)
4. `frontend/messages/de.json` — Master für Übersetzungs-Keys; pull-up bei jeder neuen UI-String
5. `frontend/i18n/request.ts` — Locale-Resolution & Cookie-Logik
6. `backend/app/locale.py` + `backend/app/errors.py` — Backend-i18n (Resolver + DE/EN-Dict mit ContextVar-Middleware)
7. `olares/OlaresManifest.yaml` — Plattform-Spec
8. `scripts/check-chart.sh` — die 9 Phase-4-Lessons als Code

## Letzter Commit + GH State (zum Stand dieses Handoffs)

```bash
git log --oneline -5
gh run list --workflow=release.yml --limit 3
```

Sollte **v0.1.49** als jüngsten Tag zeigen. Tag-Liste seit
v0.1.34: 0.1.35 → … → 0.1.47 → 0.1.48 → 0.1.49. Box läuft
(Stand Doku-Update) noch auf v0.1.48 (Helm-Rev 34) — v0.1.49 ist
nur Frontend+Whisper-Code-Change, keine Migration nötig.

## Cmd-Shift-R nicht vergessen

Nach jedem Frontend-Deploy: **Browser-Cache hard-reloaden**
(Cmd-Shift-R / Ctrl-Shift-R). Der Service-Worker hält sonst das alte
Bundle. (v0.1.44 ist reines Whisper-Service-Update — Frontend-Bundle
unverändert, hard-reload trotzdem nicht schaden.)
