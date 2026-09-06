# Next-Session-Starter

Diese Datei ist der **Aufschlag-Prompt für ein frisches Kontextfenster**.
Kopiere unten alles unter „— Prompt-Anfang —" in das neue Chat-Fenster.

---

## — Prompt-Anfang —

Lies dich ein:

1. **`CLAUDE.md`** — Projekt-Briefing, Olares-Constraints, Tech-Stack.
2. **`docs/HANDOFF.md`** — Status + Learnings. **Besonders der Header
   oben ($1) sowie §7g „v0.1.14 → v0.1.16 Lessons".**

**Stand:** **v0.1.81 läuft auf der Box** (Helm-Rev 5 nach der
Neuinstallation, verifiziert 19.8.2026: alle fünf Pods auf 0.1.81-Images,
sechs von sechs Health-Checks grün) und liegt als Tag + Chart im Repo
sowie im AIMighty-Markt. Box: `olares@192.168.1.17` (Olares-User
`kaivostudio`, Box-URL `https://e5d605f3.kaivostudio.olares.de`).

**⚠️ Bevor du am LLM etwas änderst:** Der Chart hat seit v0.1.72
**absichtlich keinen Vorgabewert** für `LLM_BASE_URL`. Der clusterinterne
Weg zu LiteLLM antwortet nicht (Envoy davor verlangt einen
Authelia-Token), und die öffentliche Adresse hängt an einer App-Kennung,
die erst bei der Installation vergeben wird — jeder geratene Wert ist beim
nächsten Kunden falsch. Der Nutzer trägt sie unter `/einstellungen` ein;
bis dahin sagt die App das offen, statt in einen Verbindungsfehler zu
laufen. **Einen leeren API-Schlüssel nie zu `Bearer ` zusammensetzen** —
dafür gibt es `llm_config.auth_header()`. Details im HANDOFF-Header.

Feature-Set:

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
- **Schauerfunktion / Quick-Capture (v0.1.50)** — neue Route `/idee`
  mit Car-Mode-UI (schwarzer Vollbild, Riesen-Mic-Button,
  Single-Tap-Toggle, Wake-Lock, Vibration). Neues System-Template
  „Schnellnotiz" (00000005) mit schlankem Schema (`kerninhalt`,
  `naechste_schritte`, `kontext`). Backend-`quick_mode`-Flag setzt
  Template hart + zwingt Webhook-Auto-Dispatch (für Friction-Free-UX).
  PWA-Shortcut „Idee aufnehmen" für Home-Screen-Long-Press.
  Volle Pipeline bis zum Webhook-Versand (bis ein Empfänger steht:
  Retry-Queue).
- **Whisper-env-prefix + JSON-Unwrap (v0.1.52)** — `env_prefix="WHISPER_"`
  in den Whisper-Settings (lief vorher als `tiny` statt `large-v3`!),
  `_unwrap_json_codeblock()` strippt Markdown-Code-Fences aus
  LLM-Antworten vor `json.loads`.
- **/idee Visual-Polish (v0.1.53–v0.1.56)** — ShowerHead-Header-Trigger,
  und drei Anläufe gegen einen CSS-Bug (schwarzer Vollbild-BG wurde nicht
  gemalt): `background`-Shorthand gesplittet → Hex-Literale statt CSS-Vars
  → `.quick-capture-shell` mit `!important` in globals.css.
- **Health-Checks + LLM-Verbindungstest (v0.1.57–v0.1.60)** —
  `/health/{whisper,llm,embeddings}` pingen jetzt echte Services statt
  `"status": "skipped"` zurückzugeben; `/health/ollama` ersatzlos weg
  (LiteLLM-Umstieg). LLM-Check nutzt `GET {llm_base_url}/models` mit 3 s
  Timeout. „Verbindung testen" in `/einstellungen` testet die **aktuellen
  Formularwerte** statt der gespeicherten — testen vor dem Speichern
  funktioniert. numpy als explizite Backend-Dependency nachgetragen.
- **Repo-Hygiene (18. August 2026, kein Release)** — Root-`OlaresManifest.yaml`
  war aus dem Release-Prozess gefallen (Markt verlangt zwei synchrone
  Kopien); `release.sh` bumpt jetzt beide, `check-chart.sh` failt bei
  Drift. `AGENTS.md` committed. 4 Ruff-Violations gefixt, die den
  `ci`-Workflow seit v0.1.59 rot hielten.

**Am 19. August — v0.1.76 bis v0.1.81:**

- **Manifest auf apiVersion v3** (v0.1.76), **Spracherkennung als
  eintragbarer Endpunkt** (v0.1.77) — ohne Eintrag transkribiert weiter
  der mitgelieferte Whisper, kein Ton verlässt die Box. `/health/stt`
  meldet `mode=local` oder `mode=external`.
- **Insilo liegt im AIMighty-Markt** (`aimighty-market.pages.dev`),
  Eintrag in `functions/_apps.ts` + Chart base64 in `functions/_lib.ts`.
- **Eine Deinstallation über den Markt löscht die Datenbank.** `/app/data`
  überlebt, die Datenbank nicht — samt neuer Org-Kennung, wodurch
  vorhandene Aufnahmen unter `audio/<org-id>/` in der Luft hängen.
  Antwort: `backend/app/konfiguration.py` schreibt einen Abzug der
  Einrichtung neben das Audio (0600, **enthält Zugangsdaten**) und liest
  ihn beim Start zurück, wenn die Datenbank leer ist. **Er funktioniert
  erst ab v0.1.81** — davor zielte er auf `APP_DATA_DIR`, also den
  Host-Pfad des Volumes, und fragte eine gedroppte Spalte ab.
- **13 herrenlose Aufnahmen wieder angehängt** (19.8., kein Release):
  Besprechungszeilen unter der laufenden Organisation angelegt, Dateien
  in deren Verzeichnis kopiert (die Audio-Ausgabe prüft `user.org_id`
  gegen die Kennung im Pfad), neu transkribiert — 10 mit Text und
  Zusammenfassung, 3 nachweislich stumm (auch `large-v3` findet dort kein
  Wort). Die alten Kopien sind nach sha256-Abgleich gelöscht. Herkunft
  steht in `meetings.metadata.wiederhergestellt`.

**Seit dem 18./19. August — v0.1.66 bis v0.1.74, auf der Box:**

- **Rebrand auf das AImighty-Designsystem** — Geist-Schriften, Hanseatenblau,
  dreiteilige Hülle, Hell- und Dunkelmodus. Werte in
  `frontend/app/globals.css`, Regeln in `docs/DESIGN.md`.
- **Datenschutz-Nachweis** — `GET /api/v1/egress` misst, was die Box
  tatsächlich verlässt; Nachweis unten in der Navigation, Detailansicht
  unter `/datenschutz`. Migration **0014** zählt gesendete Webhook-Bytes.
- **Aufnahme-Welle** — Pegelverlauf des echten Mikrofonsignals während
  der Aufnahme, logarithmisch skaliert (v0.1.66).
- **Wappen + vollständiger Icon-Satz** — PWA, Home-Bildschirm,
  Olares-Kachel; `icons/` war vorher leer (v0.1.68). In v0.1.71 auf das
  überarbeitete Figma-Zeichen gewechselt: Wappen jetzt in zwei Fassungen
  (hell/dunkel), maskable-Symbol mit Sicherheitsabstand.
- **Herkunftsvermerk** unten in der Navigation, verlinkt auf aimighty.de
  (v0.1.69).
- **Ehrliche Erst-Einrichtung des Sprachmodells (v0.1.72/0.1.73)** — kein
  erfundener Vorgabe-Endpunkt mehr. Ohne eingetragene Adresse laufen
  Aufnahme und Transkription weiter, die Zusammenfassung unterbleibt
  (Status bleibt `transcribed`), `/health/llm` meldet `not_configured`,
  und Einstellungen wie Aufnahme-Seite sagen, was fehlt. `/health/llm`
  liest die wirksame Adresse aus der Datenbank, nicht die
  Deployment-Vorgabe (v0.1.73). Der Verbindungstest kommt mit leerem
  Schlüsselfeld zurecht (v0.1.74) — die Kopfzeile baut
  `llm_config.auth_header()`, nie von Hand.
- **Datenschutz-Nachweis unterscheidet eigene Box von Fremdanbieter**
  (v0.1.70) — sonst hätte er dauerhaft gewarnt, obwohl das Modell auf
  derselben Maschine läuft.
- **⚠️ Ein Upgrade friert die Werte ein — und meldet trotzdem Erfolg.**
  Olares spielt beim Aktualisieren die bei der *Installation*
  gespeicherten Werte wieder ein und übernimmt die Vorgaben des neuen
  Charts nicht. Zweimal darauf hereingefallen: v0.1.66 (Chart 0.1.66 bei
  Images 0.1.56, per Direkt-Upgrade) und v0.1.80 (Chart 0.1.80 bei Images
  0.1.77, über den Markt — Kachel, `helm history` und alle sechs
  Health-Checks meldeten die neue Version, nur die Pods trugen die alten
  Bilder). **Seit v0.1.81 hängt der Image-Tag an `.Chart.AppVersion`**,
  nicht an `.Values.images.*.tag`; die Metadaten kommen frisch an, die
  Werte nicht. Ein `helm upgrade --reuse-values` reicht damit wieder.
  **Trotzdem danach immer nachsehen, was wirklich läuft** — die
  Erfolgsmeldung beweist nichts:
  `kubectl get pods -n insilo-kaivostudio -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}'`

**Nächste Iteration: der erste Zugang einer frischen Box**

Die Absicherung des Backends ist erledigt und ausgerollt (Torwächter,
erzwungene Zeilensicherheit, keine Selbstbedienung mehr) — Stand im
HANDOFF-Kopf unter „Torwächter und Zeilensicherheit“.

Genau daraus folgt der nächste offene Punkt: **eine frisch installierte
Box sperrt ihren ersten Nutzer aus.** `auto_provision` ist Vorgabe
`False`, das Chart setzt `INSILO_AUTO_PROVISION` nie, und
`konfiguration.wiederherstellen` greift nur, wenn
`/app/data/konfiguration.json` schon existiert. Bei einer echten
Neuinstallation legt also niemand den ersten Nutzer an; der erste Aufruf
endet mit 401 „Unknown identity“. `docs/HANDBUCH.md` Abschnitt 2
dokumentiert bis auf Weiteres den Weg über `psql`.

Die naheliegende Lösung — beim leeren Bestand wird die erste Identität
Inhaberin einer neuen Organisation, jede weitere unbekannte weiter 401 —
rührt an genau der Stelle, die Kai zumachen wollte. **Erst fragen, dann
bauen.**

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
ssh olares@192.168.1.17
# Helm braucht: KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

Volle Pipeline für Box-Update:
```bash
scp dist/insilo-0.1.X.tgz olares@192.168.1.17:/tmp/
ssh olares@192.168.1.17 \
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
| Version | **v0.1.87** auf der Box, verifiziert 6.9.2026 (Helm-Rev 11, alle fünf Pods auf 0.1.87). |
| Plattform | Olares OS (k3s) auf `192.168.1.17` |
| Box-User | `kaivostudio` |
| URL | `https://e5d605f3.kaivostudio.olares.de` |
| Container | `ghcr.io/ska1walker/insilo-{frontend,backend,whisper,embeddings}:0.1.87` |
| Health | `/health`, `/health/db`, `/health/whisper`, `/health/llm`, `/health/embeddings` — alle echt seit v0.1.57 |
| LLM | Per-Org konfigurierbar via `/einstellungen` (**kein Vorgabewert**, siehe HANDOFF-Kopf); Qwen2.5-tuned Prompts mit Few-Shot, 5-Sprachen-Prompts (v0.1.46) |
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
| Migrationen | 17 im Repo (0001–0017), alle auf der Box angewendet |
| Markt-Bilder | `markt/` — Aufmacher + fünf Tafeln, 1920×1080, neu bauen mit `bash scripts/markt-bilder.sh`; im OlaresManifest verlinkt |
| Kundendoku | `docs/HANDBUCH.md` — das einzige Dokument in `docs/`, das nicht für die Werkstatt ist |

## Offene Issues / Bekannte Stolpersteine

- **Online-Builds dauern** ~6-9 min weil Whisper-Image ~1.2 GB (torch + speechbrain). Akzeptabel.
- **GHCR-Login kann timeout** machen (transient). Re-run der failed jobs reicht meist (`gh run rerun <id> --failed`).
- **Service-Worker-Cache** im Browser: nach jedem Frontend-Deploy einmal Cmd-Shift-R, sonst sieht User alte Version.
- **Kein PodDisruptionBudget — bitte auch keins einführen.** Alle fünf
  Deployments laufen mit `replicas: 1` auf einer Ein-Knoten-Box; ein PDB
  mit `minAvailable: 1` würde `kubectl drain` blockieren, ohne
  Verfügbarkeit zu gewinnen. Die leere `pdb.yaml`-Hülle (v0.1.57 rein,
  v0.1.58 geleert) ist gelöscht. Begründung im HANDOFF-Header.
- **Box-Version läuft der Repo-Version davon.** Seit v0.1.49 ist kein
  Deploy mehr in der Doku festgehalten. Nach jedem Box-Update den Stand
  hier und im HANDOFF nachtragen — sonst rät die nächste Session.

## Wichtige Dateien zum Lesen vor dem ersten Commit

1. `CLAUDE.md` — Briefing (insbes. neue Sprachregel)
2. `docs/HANDOFF.md` — Status + Lessons (Header-Block oben: Manifest-Drift +
   PDB-Warnung; v0.1.44-Block für die Decoder-Lesson)
3. `docs/DESIGN.md` — Designsystem (AImighty: Hanseatenblau/Gold, formelle Anrede)
4. `frontend/messages/de.json` — Master für Übersetzungs-Keys; pull-up bei jeder neuen UI-String
5. `frontend/i18n/request.ts` — Locale-Resolution & Cookie-Logik
6. `backend/app/locale.py` + `backend/app/errors.py` — Backend-i18n (Resolver + DE/EN-Dict mit ContextVar-Middleware)
7. `OlaresManifest.yaml` **und** `olares/OlaresManifest.yaml` — Plattform-Spec.
   Zwei Kopien, müssen synchron bleiben (Markt-Anforderung, siehe
   MARKET_SOURCE_PLAYBOOK). `release.sh` bumpt beide, `check-chart.sh` prüft es.
8. `scripts/check-chart.sh` — die Phase-4-Lessons als Code (inkl. Manifest-Sync)

## Letzter Commit + GH State (zum Stand dieses Handoffs)

```bash
git log --oneline -5
gh run list --limit 5
```

Sollte **v0.1.65** als jüngsten Tag zeigen. v0.1.61–v0.1.65 sind reine
Chart-Releases (Markt-Validierung, siehe HANDOFF-Header) — der letzte
Release mit Code-Änderung ist v0.1.60. **Der `ci`-Workflow ist seit
`28f7e63` wieder grün** — er war von v0.1.59 bis dahin durchgehend rot
(4 Ruff-Violations),
während `release.yml` unbeeindruckt weiter Images baute. Wenn `ci` rot
ist: `gh run view <id> --log-failed` und nicht darauf verlassen, dass ein
grüner `release`-Run Entwarnung bedeutet.

## Cmd-Shift-R nicht vergessen

Nach jedem Frontend-Deploy: **Browser-Cache hard-reloaden**
(Cmd-Shift-R / Ctrl-Shift-R). Der Service-Worker hält sonst das alte
Bundle.
