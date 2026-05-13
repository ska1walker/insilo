# Handoff — Stand & Learnings (Mai 2026, **letzte Aktualisierung: 13. Mai**)

> Dieses Dokument bringt eine neue Claude-Session (oder einen frischen Mitarbeiter)
> in **<2 Minuten** auf den Stand. Kein Marketing, nur Substanz.
>
> **Stand 13. Mai 2026 (Abend, ~16h gearbeitet):** Massiver Fortschritt durch den ganzen Tag.
> Insilo läuft **technisch erfolgreich** auf der Olares-Box mit vollem BFL-Flow
> (Application-CR, ns-owner Label, app-np NetworkPolicy, alle Pods Ready). Aber:
> der PWA-Frontend-Backend-Datenflow ist noch nicht 100% — Backend Envoy weist
> Next.js-Proxy-Calls mit 401 zurück, weil interne Calls keine Authelia-Cookies haben.
>
> **Letzter Stand v0.1.12** (gepackt, gepusht, noch NICHT installiert):
> - **api-Entrance entfernt** aus OlaresManifest → Backend-Pod hat keinen Envoy-Sidecar mehr
> - Frontend bleibt mit Entrance + Envoy (Authelia-geschützt)
> - Next.js Server-Proxy (rewrites) ruft direkt `http://insilo-backend:8000` ohne Auth-Hop
> - Backend FastAPI liest X-Bfl-User-Header der via Frontend-Envoy injiziert + von Next.js weitergeleitet wird
>
> Nächste Action für neue Session: User uploadet `~/Downloads/insilo-0.1.12.tgz`
> via Olares Market UI ("Upload custom chart") → erste End-to-End-Verifikation.
>
> Siehe §7f für die Phase-4b-Learnings (Dockerfile-Buildtime-Bake, Envoy-Auth-Loop, Helm-Upgrade-Workaround).

---

## 1. Wo wir gerade stehen

| Phase | Status | Lokal | Auf Olares |
|---|---|---|---|
| **1 — Audio-Pipeline** (Aufnahme → Whisper-Transkript) | ✅ live | ✅ läuft | ✅ Pod läuft (1/1 Running getestet 13. Mai) |
| **2 — LLM-Summary** (Qwen via LiteLLM) | ✅ live | ✅ läuft | ✅ Worker connected sich erfolgreich (Redis-Fix v0.1.2) |
| **3 — RAG / „Ask"** (BGE-M3 + pgvector + grounded answers) | ✅ live | ✅ läuft | ✅ Embeddings-Pod läuft (1/1 Running) |
| **4 — Olares-Paketierung** | 🟡 v0.1.12 chart ready (uninstalled state) — User muss `~/Downloads/insilo-0.1.12.tgz` uploaden, siehe §7f | Install via "Upload custom chart" funktioniert (haben wir verifiziert mit v0.1.9-v0.1.11), Application CR + ns-owner Label kommen automatisch | |
| 5 — Pilot-Deployment | nach v0.1.12 End-to-End-Test, ETA ~1 Woche | | |

**Letzter konkreter Stand (Commit ggf. noch ungepusht, lokal Chart v0.1.5):**

- 4 Container-Images public auf `ghcr.io/ska1walker/insilo-*:0.1.0` (linux/amd64). Ollama-Image **entfernt** — wir nutzen LiteLLM stattdessen.
- Helm-Chart-Iterationen: 0.1.0 → 0.1.5 (siehe §7c für Fix-Historie). Aktuell `dist/insilo-0.1.5.tgz` (~34 KB).
- Auf Olares: 3 von 5 Pods laufen (worker, whisper, embeddings). 2 von 5 hängen permanent am Olares-injected `check-auth` Init-Container.
- LiteLLM-Cross-App-Calls **architekturell verifiziert** — Worker-Pod erreichbar, hat echtes Redis-Passwort, wartet auf Tasks.
- Repo `ska1walker/insilo` ist **public**.

**Aktuelle Aufgabe:** Strategische Entscheidung treffen — siehe §7c "Drei Wege ab hier" und §9.

---

## 2. Architektur in 30 Sekunden

**Insilo** = datensouveräne Meeting-Intelligenz-PWA für deutschen Mittelstand.
**Plattform** = Olares OS (K8s-basiert) beim Kunden. Olares stellt System-Middlewares (PostgreSQL, KVRocks, MinIO, Authelia+Envoy) — wir bauen die nicht selbst. Plus: für **LLM** nutzen wir die Olares-LiteLLM-Gateway-App des Users — kein eigenes Ollama mehr.

```
PWA (Next.js) → Backend (FastAPI, X-Bfl-User-Auth via Envoy)
                  ↓ Celery
                  ↓ KVRocks (Redis-API) als Broker
                  ↓
       ┌──────────┴──────────┐
       ↓                     ↓
Whisper-Svc (CPU)    Embeddings-Svc (BGE-M3 CPU)
(faster-whisper)
       ↓                     ↓
              Postgres + pgvector + MinIO
              (Olares System-Middlewares)
                            +
       Backend ─── Cross-App-Call ──→ LiteLLM-Gateway
                                      ↓ (User's andere Olares-App)
                                      Qwen 36B Vision (llama.cpp)
```

**Auth:** Kein eigener Code. Envoy-Sidecar vor jedem Pod prüft Authelia-Token, injiziert `X-Bfl-User` Header. Lokal mocken wir den Header. **Cross-App-Calls (LiteLLM):** Olares verlangt `permission.provider` im Manifest mit `{appName, providerName, podSelectors}`.

**DB:** asyncpg + SQLAlchemy 2.x. Schema in `supabase/migrations/` (Ordnername historisch, nichts mit Supabase zu tun).

**LLM-API:** OpenAI-kompatibel (`/v1/chat/completions`, Bearer-Token). Funktioniert identisch gegen LiteLLM (auf Olares) und Ollama lokal (Apple Metal, exposed seine OpenAI-API auf `:11434/v1`).

---

## 3. Repo-Struktur (gelandete Files)

```
/
├── CLAUDE.md                  # Briefing — komplette Architektur-Doku
├── docs/
│   ├── ARCHITECTURE.md        # Datenfluss, Komponenten-Verantwortlichkeiten
│   ├── PLATFORM.md            # Langfristige Multi-App-Vision (CallList, MaklerOS, …)
│   ├── ROADMAP.md             # Phasen 1-6
│   ├── DEPLOYMENT.md          # Olares-Paketierung, Updates
│   ├── DESIGN.md              # Designsystem (Weiß/Schwarz/Gold)
│   ├── SECURITY.md
│   └── HANDOFF.md             # ← diese Datei
│
├── frontend/                  # Next.js 15 App Router PWA
│   ├── app/
│   │   ├── page.tsx           # Meeting-Liste
│   │   ├── aufnahme/page.tsx  # MediaRecorder + Template-Picker
│   │   ├── m/[id]/page.tsx    # Detail + Audio-Player + Transkript + Summary
│   │   ├── ask/page.tsx       # RAG-Chat über Meeting-Archiv
│   │   ├── style/page.tsx     # Design-System-Showcase (interne Referenz)
│   │   ├── api/health/route.ts
│   │   ├── globals.css
│   │   └── layout.tsx
│   ├── components/{status-pill,summary-view,recording-indicator,service-worker-register}.tsx
│   ├── lib/{db.ts,format.ts}
│   ├── lib/api/{client,meetings,templates,ask}.ts
│   ├── public/{manifest.json,sw.js}
│   └── Dockerfile
│
├── backend/                   # FastAPI + Celery
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan, /health/*
│   │   ├── config.py          # Pydantic Settings (env vars)
│   │   ├── db.py              # asyncpg pool
│   │   ├── storage.py         # boto3 MinIO/S3 wrapper
│   │   ├── auth.py            # X-Bfl-User dependency + auto-provisioning
│   │   ├── worker.py          # Celery app (redis broker)
│   │   ├── routers/
│   │   │   ├── meetings.py    # GET/POST /api/v1/meetings + /recordings
│   │   │   ├── templates.py   # GET /api/v1/templates
│   │   │   └── search.py      # POST /api/v1/search + /ask (RAG)
│   │   └── tasks/
│   │       ├── transcribe.py  # → Whisper
│   │       ├── summarize.py   # → Ollama
│   │       └── embed.py       # → BGE-M3
│   └── Dockerfile
│
├── services/
│   ├── whisper/   {pyproject.toml, Dockerfile, app/main.py}
│   └── embeddings/{pyproject.toml, Dockerfile, app/main.py}
│
├── supabase/                  # nur lokale Dev — Name historisch
│   ├── migrations/
│   │   ├── 0001_initial_schema.sql    # 11 Tabellen inkl. public.users, meetings, transcripts, summaries, meeting_chunks
│   │   └── 0002_rls_policies.sql      # RLS via app.current_user_id
│   └── seed.sql               # 4 System-Templates
│
├── olares/                    # Helm-Chart für Olares-Markt
│   ├── Chart.yaml             # name=insilo, version=0.1.0, appVersion=0.1.0
│   ├── OlaresManifest.yaml    # metadata, entrances, middleware, permission, spec
│   ├── values.yaml            # image-tags, models, app-config
│   ├── values-olares-stub.yaml # für lokales helm-lint
│   ├── icon-256.png           # 256x256 PNG, gehostet via GitHub raw
│   └── templates/
│       ├── deployment-{frontend,backend,worker,whisper,ollama,embeddings}.yaml
│       └── services.yaml
│
├── docker-compose.yml         # lokale Dev: postgres + redis + minio + whisper + embeddings
├── .env.example
├── .github/workflows/
│   ├── ci.yml                 # type-check + ruff
│   └── release.yml            # baut + pusht 4 Images auf tag v*.*.*
└── dist/insilo-0.1.0.tgz      # gepackter Helm-Chart (gitignored)
```

---

## 4. Lokales Dev-Setup (was läuft auf dem Mac)

| Service | Wo | Port |
|---|---|---|
| Postgres + pgvector | `insilo_pg` (docker) | 5432 |
| Redis (KVRocks-Stand-in) | `insilo_redis` (docker) | 6379 |
| MinIO | `insilo_minio` (docker) | 9000 (console 9001) |
| Whisper | `insilo_whisper` (docker, faster-whisper `tiny` CPU) | 8001 |
| Embeddings | `insilo_embeddings` (docker, BGE-M3 CPU) | 8002 |
| Ollama | **nativ via brew, Apple Metal** (nicht Docker — Docker auf Mac hat keinen GPU) | 11434 |
| Backend | `uvicorn` nativ in venv | 8000 |
| Worker | `celery` nativ in venv | — |
| Frontend | `next dev` nativ | 3000 |

Starten:
```bash
docker compose up -d
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload &
cd backend && source .venv/bin/activate && celery -A app.worker worker --loglevel=info &
ollama serve &
cd frontend && npm run dev
```

Migrationen lokal einspielen (einmalig):
```bash
docker exec -i insilo_pg psql -U insilo -d insilo < supabase/migrations/0001_initial_schema.sql
docker exec -i insilo_pg psql -U insilo -d insilo < supabase/migrations/0002_rls_policies.sql
docker exec -i insilo_pg psql -U insilo -d insilo < supabase/seed.sql
```

MinIO-Bucket einmalig:
```bash
docker run --rm --network host --entrypoint sh minio/mc \
  -c "mc alias set local http://localhost:9000 insilo_dev insilo_dev_secret && mc mb local/insilo-audio --ignore-existing"
```

---

## 5. Konventionen & Branding

- **App-Name (tech):** `insilo` durchgängig lowercase. Olares-Linter-Regex: `^[a-z0-9]{1,30}$`, Folder/Chart.name/metadata.name müssen identisch sein.
- **Display-Name:** „Insilo" (kapitalisiert) im OlaresManifest title, PWA-Manifest, Doc-Headlines.
- **Owner/Brand:** Kai Böhm / kaivo.studio. Vertrieb via aimighty.de.
- **GitHub-Org:** `ska1walker` (User-Account, nicht Org). Image-Pfade: `ghcr.io/ska1walker/insilo-*`.
- **Sprache:** UI/Docs auf Deutsch (Sie-Form, formell). Code + Commit-Messages auf Englisch.
- **Designsystem:** Weiß `#FFFFFF`, Schwarz `#0A0A0A`, Gold `#C9A961` (sparsam!). Lexend Deca + Inter + JetBrains Mono. Details in [`docs/DESIGN.md`](DESIGN.md).
- **Anti-Patterns:** keine Gradients, kein Glassmorphism, kein Lila, kein Card-in-Card, keine AI-Sparkles.

---

## 6. Olares-Constraints — kritisch für jedes Chart-Update

1. **Keine eigene Auth.** Envoy-Sidecar validiert vorher. User-Identität aus Header `X-Bfl-User`.
2. **Keine hostNetwork / NodePort / LoadBalancer.** Nur `ClusterIP` + deklarierte `entrances`.
3. **Keine ClusterRole-Bindings, keine Cross-Namespace-Direktcalls.** Cross-App-Zugriff nur via Service-Provider-Pattern.
4. **Storage nur in `/app/data/`, `/app/cache/`, `/app/Home/`.**
5. **Image-Naming:** `metadata.name` literal, **nicht** `{{ .Release.Name }}`.
6. **Folder-Name = `metadata.name` = `metadata.appid` = `Chart.yaml.name`** — alle vier identisch.
7. **DB-Connection-Vars werden injiziert** durch Olares wenn `middleware: postgres: {…}` deklariert ist. Lokal mocken wir das in `olares/values-olares-stub.yaml`.

### Wie Olares die Middleware-Values genau injiziert (verifiziert auf der Box)

| Manifest-Deklaration | Was Olares injiziert | Template-Referenz |
|---|---|---|
| `redis: { password, namespace }` | `.Values.redis.{host,port,password,namespace}` als **einzelne Strings** | `{{ .Values.redis.namespace }}` |
| `postgres: { username, databases: [{name, …}] }` | `.Values.postgres.{host,port,username,password}` + `.Values.postgres.databases.<name>` als **Map keyed by db-name** | `{{ .Values.postgres.databases.insilo }}` |
| `permission: { appData: true }` | `.Values.userspace.appData` als Pfad-String | `mountPath: /app/data` + `hostPath.path: {{ .Values.userspace.appData }}` |
| `permission: { provider: [{appName, providerName, podSelectors}] }` | Envoy-Sidecar erlaubt Cross-Namespace-Calls zum angegebenen Service | URL-Pattern: `http://<svc>.<appName>-{{ .Values.bfl.username }}.svc.cluster.local` |
| automatisch | `.Values.bfl.username`, `.Values.user.zone`, `.Values.cluster.arch`, `.Values.domain.<entranceName>` | siehe Bundle-Templates |

### Cross-App-Services auf der Olares-Box (kaivostudio @ olares.de)

| Service | Cluster-DNS | Port | Auth | Was es serviert |
|---|---|---|---|---|
| **LiteLLM** (LLM-Gateway) | `litellm-svc.litellm-kaivostudio.svc.cluster.local` | `80` (→ pod 4000) | `Authorization: Bearer sk-1234` | OpenAI-kompatibel, routet auf `qwen36a3bvisionone` und andere LLM-Apps |
| Qwen 36B Vision (llama.cpp) | `qwen36a3bvisionone.qwen36a3bvisionone-kaivostudio.svc.cluster.local` | `8080` | Envoy-managed | OpenAI-API, direkt — meist via LiteLLM aufrufen |
| Open WebUI | `openwebui.openwebui-kaivostudio.svc.cluster.local` | `8080` | Envoy-managed | UI, nicht für API-Calls genutzt |
| LiteLLM Ingress | `litellmingress.litellm-kaivostudio.svc.cluster.local` | `8080` | Envoy-managed | Admin-UI |

**Wichtig:** Anonyme Pods (`kubectl run --rm curlpod`) bekommen vom Envoy-Sidecar `cannot get user name from header` zurück. Tests nur aus schon-managed Pods (`kubectl exec deployment/openwebui ...`). Im Produktiv-Betrieb haben unsere Insilo-Pods den richtigen Sidecar automatisch durch die `permission.provider`-Deklaration.

---

## 7. Learnings & Stolpersteine (chronologisch durch Phase 4)

| Problem | Ursache | Fix |
|---|---|---|
| Frontend-Image: `addgroup -g 1000` failed | `node:alpine` shippt `node`-User auf UID 1000 | `deluser node` vor `addgroup` in `frontend/Dockerfile` |
| Frontend-Build: tailwind fehlt im next build | `npm ci --omit=dev` ließ Tailwind weg | Stage `deps` → `npm ci` (mit dev deps), Next standalone bündelt nur nötiges |
| Backend-Image-Build: „package directory 'app' does not exist" | `pyproject.toml.packages=["app"]` aber app/ nicht in builder kopiert | `COPY app ./app` vor `pip install .` (auch für services/whisper, services/embeddings) |
| GHCR-Images privat → Olares kann nicht pullen | Default-Visibility ist „inherit from repo" → privat | Pro Package: Settings → Danger Zone → Change visibility → Public |
| Safari verbiegt `.tgz` zu `.tar` (42 KB statt 8 KB) | „Sichere Dateien nach Laden öffnen" entpackt gzip | `gh release download v0.1.0 -R ska1walker/insilo -p 'insilo-0.1.0.tgz' --clobber` |
| Olares Install hängt bei „Adding chart to local source" / `downloadFailed` ohne Detail | `metadata.icon`-URL auf `raw.githubusercontent.com/ska1walker/insilo/main/...` lieferte 404 weil **Repo privat** | Repo public schalten — Icon dann unter HTTP 200 erreichbar |
| `insilo-embeddings`-Image war 2.8 GB | `sentence-transformers` zieht CUDA-PyTorch transitiv | In `services/embeddings/Dockerfile` zuerst `pip install --index-url https://download.pytorch.org/whl/cpu torch` — schrumpft auf 403 MB |
| OlaresManifest `helm template`: nil pointer `.Values.postgres.host` | `middleware:` block fehlte komplett | Block ergänzt in `olares/OlaresManifest.yaml`: `postgres` mit databases + extensions, `redis` mit namespace |
| `helm template` braucht Olares-injected values lokal | Olares injiziert zur Install-Zeit | `olares/values-olares-stub.yaml` für `helm lint` / `helm template` Dev |
| Migration 0001 zirkuläre FK | `meetings.template_id references templates(id)` inline, aber templates erst später angelegt | Inline-FK weg, ALTER TABLE nach templates-CREATE |
| Bundle-Adoption (großer Pivot Mai 2026) | Vorheriger Stand war Supabase-zentriert; Olares ist tatsächlich Plattform | Komplette Adoption des `insilo-projekt-bundle.zip`-Inhalts: Olares-native, Authelia statt Supabase-Auth, asyncpg statt Supabase-Client. Siehe Commit `52c798b`. |
| **Olares hängt bei `downloadFailed` ohne UI-Detail** — wirkt wie Image-Pull-Timeout, war aber Helm-Template-Render-Fehler | Bundle-Annahme: `.Values.redis.namespaces.<name>` (Plural+Map). Realität: `.Values.redis.namespace` als Single-String. Olares retried den State NICHT, bleibt stur in `downloadFailed`. | `deployment-{backend,worker}.yaml`: `.Values.redis.namespaces.insilo` → `.Values.redis.namespace`. Commit `d38877e`. **Generell: Bundle-Annahmen über injected-value-shape immer gegen `kubectl logs -n os-framework app-service-0` validieren.** |
| `App closed. Cause: insufficient vram` nach erfolgreichem Pod-Start | Bundled Qwen 14B (10 GB VRAM) + Whisper large-v3 (3 GB) = 13 GB. GPU der Box ist nominell 24 GB, aber Time-Slicing reserviert leere Slots für andere gepinnte Apps. `nvidia-smi`: 22.5/24.5 GB belegt, aber nur 324 MB von einem echten Prozess. | Drei-Schritte-Refactor: (1) Qwen 14B → 7B (Commit `710e0b7`). (2) Eigenes Ollama-Deployment komplett raus, LiteLLM-Gateway nutzen (`a446273`). (3) Whisper auf CPU, 0 GPU-Slot (`363e2e9`). Insilo läuft jetzt ohne jede GPU-Reservierung — Trade-off: Whisper 5× langsamer (5-Min-Audio = 1-2 Min Transkription statt 20 s). |
| `state=stopped, Reason=Unschedulable` (vor Whisper-CPU-Fix) | K8s konnte Pod nicht placen weil GPU-Slot komplett vergeben. Single-Node-Olares, andere Apps (Open WebUI, Qwen Vision, LiteLLM) hatten alle GPU-Slots besetzt. | Whisper-Deployment: `WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`, `nvidia.com/gpu` raus aus resources. Bumped CPU-request auf 2 cores. Commit `363e2e9`. |
| Safari-Quick-Look entpackt `.tgz` zu nutzlosem `.tar` | macOS-Default: „Sichere Dateien nach Laden öffnen" entpackt gzip. Olares-Linter ablehnt mit „unexpected EOF" | Direkt-Download mit auth: `gh release download v0.1.0 -R ska1walker/insilo -p 'insilo-0.1.0.tgz' --clobber`. Anonymes curl liefert 404 weil Repo damals private war (vor Public-Switch). |
| Olares blockiert ad-hoc `kubectl run curlpod` mit „cannot get user name from header" | Envoy-Sidecar auf jedem managed-Pod verlangt `X-Bfl-User` Header. Random-Pods aus `default` namespace haben den nicht. | Tests aus schon-managed Pod (`kubectl exec -n openwebui-kaivostudio deployment/openwebui -c openwebui -- curl ...`) oder direkt aus eigenem App-Pod nach Install. |
| **`Chart.yaml.version` ≠ `OlaresManifest.metadata.version`** → Upload-400 mit „must same" | Bei jedem Chart-Bump müssen BEIDE Felder synchron sein. | In Chart.yaml UND OlaresManifest.yaml gleichzeitig bumpen. |
| Worker: `ModuleNotFoundError: No module named 'app.workers'` (Bundle-Template) | Bundle hatte `-A app.workers.celery_app` (Plural). Tatsächliches Modul: `backend/app/worker.py` mit Instanz `celery_app`. | `olares/templates/deployment-worker.yaml`: command `-A app.worker:celery_app` (Singular, expliziter Pfad). |
| Whisper + Embeddings: `PermissionError: '/app/cache/<x>'` als UID 1000 | Olares mountet `/app/cache` per hostPath, host-Pfad ist root-owned. Mount-Overlay schattet das `chown` aus dem Dockerfile. | Init-Container `init-chown` (busybox:1.36) mit `securityContext.runAsUser: 0` chownt den Mount auf 1000 bevor App-Container startet. Pod-Level `runAsNonRoot: true` muss raus, sonst K8s rejected den root-init. |
| Olares injiziert literal-string „auto" als Redis-Passwort, statt es zu generieren | Bundle-Template hatte `middleware.redis.password: auto` — Olares interpretiert das nicht als Trigger, sondern als Wert. | `password:`-Feld komplett aus `OlaresManifest.middleware.redis` entfernen. Olares generiert dann selbst ein Secret und injiziert via `.Values.redis.password`. **Vorbild: `searxngv2/OlaresManifest.yaml` auf der Box.** |
| `options.runAsUser: true` (Bool) bricht Olares JSON-Parser | Error: „Installation failed: failed to parse response JSON: invalid character 'i' in literal false (expecting 'l')". | Zurück zu `runAsUser: "1000"` (String). searxng's `true` ist im konditionalen Helm-Template eingewickelt, deshalb funktioniert's dort. |
| `appScope.clusterScoped: false` triggert NICHT `bytetrade.io/ns-owner` Label-Setting | Dachten das wäre der Hook. Ist es nicht. AM zeigt `App Owner: kaivostudio` und `AppScope: clusterScoped: false` korrekt parsed, aber Namespace bleibt ohne `ns-owner` Label. | Es gibt **keinen bekannten Manifest-Hook** für das Label. Siehe §7c — Sackgasse. |
| `entrances.authLevel: public` skippt NICHT den Olares-injected `check-auth` Init | Hofften das wäre der Workaround. Olares' Envoy-Sidecar-Webhook ist agnostisch zum authLevel und injiziert IMMER `check-auth` für Pods mit entrances. | Kein Workaround auf Manifest-Ebene. Siehe §7c. |
| Manuelles `kubectl label namespace … bytetrade.io/ns-owner=kaivostudio` → sofort revertiert | Ein Olares-Webhook strippt alle nicht-explicit-erlaubten `bytetrade.io/*` Labels auf Namespaces. Mehrfach getestet: `ns-owner`, `ns-shared`, `ns-type` — alle weg in <1s. | Geht nicht. Olares-Source-Code-Mod nötig. |
| Manueller Patch der `user-system-np` NetworkPolicy mit neuer ingress-rule → sofort revertiert | NetworkPolicy-Reconciler in Olares rebuildet die NP aus dem Original-Template. | Geht nicht. |

---

## 7a. Olares-Debug-Cheatsheet — wenn etwas schiefläuft

**Wichtigste Erkenntnis:** Das Olares-Studio-UI zeigt nur `downloadFailed` oder `stopped` ohne Details. Der **echte Fehler** steht in den Cluster-Logs. Zugang: **Control Hub → Terminal** im Olares-UI (eingebautes root-shell, kein externes SSH nötig).

| Was du wissen willst | Command |
|---|---|
| Wurde überhaupt ein Pod scheduled? | `kubectl get pods -A \| grep insilo` |
| Insilo's ApplicationManager-State + history | `kubectl get applicationmanagers -A \| grep insilo` |
| **Volles ApplicationManager-Detail** (Status, Reason, Messages der letzten Ops) | `kubectl describe applicationmanager insilo-kaivostudio-insilo \| tail -60` |
| **Der konkrete Fehler-String** (Template-Render-Error, Scheduling-Fehler) | `kubectl logs -n os-framework app-service-0 --tail=2000 \| grep -iE "insilo\|ERROR" \| head -60` |
| Cluster-Events der Box-Apps | `kubectl get events -A --sort-by=.lastTimestamp \| grep insilo \| tail -20` |
| Pod-Events im Insilo-Namespace (Unschedulable, ImagePullBackOff, etc.) | `kubectl get events -n insilo-kaivostudio --sort-by=.lastTimestamp \| tail -20` |
| Welche Images bereits gepullt | `crictl images \| grep -iE "insilo\|ollama"` |
| GPU-Status: was ist VRAM-belegt | `nvidia-smi` (Tipp: Time-Slicing reserviert leere Slots — `Memory-Usage` zeigt nominell viel mehr als die `Processes`-Tabelle real belegt) |
| Cross-App-Service-Test mit Auth | `kubectl exec -n openwebui-kaivostudio deployment/openwebui -c openwebui -- python3 -c "..."` (anonymous curl scheitert wegen Envoy) |
| Wo Olares hochgeladene Charts speichert | `/olares/userdata/Cache/chartrepo/v2/<user>/upload/<appname>-<version>/` |
| App-Service Namespace | `os-framework`, pod `app-service-0` |
| Market-Backend Namespace | `os-framework`, deployment `market-deployment` |

**Patterns, die oft zuschlagen:**
- `downloadFailed` ist generischer Pre-Install-Fehler — Helm-Render, Linter-Reject, Icon-404, Image-Manifest-Resolve. Detail nur in `app-service-0` Pod-Log.
- `stopped` mit `Reason: Unschedulable` heißt: Helm OK, aber K8s findet keinen Node mit den Resource-Requests. Auf Single-Node-Olares fast immer = GPU-Slot komplett vergeben.
- `App closed. Cause: insufficient vram` heißt: Pod gestartet, Modell-Load hat OOM ausgelöst — Time-Slicing teilt VRAM nicht, andere Apps hatten Slots gepinnt.

**Manuelle Operations:**

| Aufgabe | Command |
|---|---|
| ApplicationManager-State manuell setzen | `kubectl patch applicationmanager insilo-kaivostudio-insilo --type='merge' -p '{"status":{"state":"running"}}'` (wird vom Controller wieder zurückgesetzt wenn die Ressourcen-Realität nicht passt) |
| Forced Re-Reconcile | App in Studio uninstall + reinstall mit unverändertem `.tgz` (gleiche Version) |
| `.tgz` direkt zur Box bringen ohne Studio | `gh release download v0.1.0 -R ska1walker/insilo -p 'insilo-0.1.0.tgz' --clobber` auf eigener Workstation, dann via Studio-Upload hochladen |

---

## 7c. Phase-4-Sackgasse: Olares „Upload custom chart" Pfad funktioniert nicht (Stand 13. Mai 2026)

Nach ~10h Debugging und 5 Chart-Iterationen (v0.1.0 → v0.1.5) steht fest:
**Der „Upload custom chart" Pfad in Olares Market ist fundamental nicht nutzbar für Apps die System-Middlewares brauchen (Authelia, Postgres, Redis).**

### Symptom

- Helm rendert sauber, Pods werden scheduled.
- Pods OHNE Entrance (worker, whisper, embeddings): ✅ Running 1/1 nach 60s.
- Pods MIT Entrance (frontend, backend): ❌ Init:Error nach ~20s wegen check-auth.
- `check-auth` Init-Container (Olares-injected, Image `beclab/wait-for:0.1.0`) pingt `authelia-backend.user-system-kaivostudio:9091`.
- Connect timeoutet — NetworkPolicy in `user-system-kaivostudio` blockt unsere Pods.

### Root Cause

Aus dem Vergleich mit openwebui (= funktioniert) und searxngv2 (= funktioniert):

| Wo der Pfad bricht | Realität |
|---|---|
| Andere Apps haben ein `application.app.bytetrade.io/<app>-<user>-<app>` CR | Wir haben **nur** `applicationmanager` — kein `application` CR. |
| Das `application` CR triggert den BFL-Layer, das Namespace-Label `bytetrade.io/ns-owner=<user>` zu setzen | Ohne CR → kein Label → kein User-Ownership-Signal. |
| `user-system-np` NetworkPolicy erlaubt Ingress nur von Namespaces mit `bytetrade.io/ns-owner=<user>` ODER `ns-type=system` ODER `ns-shared=true` | Unser Namespace hat **keines** davon → Authelia/Redis unerreichbar. |
| Authelia-Block → check-auth Init timeoutet → backend/frontend kommen nie aus Init raus | Pods stoppen, AM-State geht zu `stopped`. |

Olares Market hat einen anderen Code-Pfad für „Submission via beclab/apps PR" als für „Upload custom chart" — Erster erstellt das `application` CR, Zweiter nicht.

### Was nicht funktioniert (alles probiert + dokumentiert in §7)

- ❌ Manuelles Namespace-Labeling — Webhook revertiert in <1s
- ❌ NetworkPolicy-Patch — Reconciler revertiert
- ❌ `appScope.clusterScoped: false` im Manifest — kein Effekt
- ❌ `authLevel: public` auf Entrances — check-auth wird trotzdem injiziert
- ❌ Studio importiert keine existierenden Charts
- ❌ `olares-cli` hat keine `app install` Commands (nur user-Management)

### Verifikation der Sackgasse

Aus dem app-service-Pod (`os-framework/app-service-0`) Quell-Logik (impliziert aus den Logs + AM-States): Die "Upload" Source erstellt nur einen `applicationmanager` mit `Source: custom` und löst kein BFL-Provisioning aus. Das BFL wartet auf `application` CRs, die nur von der Market-Pipeline erstellt werden (bei offiziellen Charts mit gültiger `submitter` + `owners` File im `beclab/apps` Repo).

### Drei Wege ab hier — Strategische Entscheidung erforderlich

| Option | Aufwand | Vorteile | Nachteile |
|---|---|---|---|
| **A) Olares Market PR** (beclab/apps) | 1-2 Wochen | „richtiger" Pfad. Insilo wird offiziell verfügbar. BFL/Labels/NetworkPolicy automatisch korrekt. | PR-Review-Zyklus. Möglicherweise muss Manifest an Olares-Standards angepasst werden (z.B. weniger restriktive Permissions). |
| **B) Plain K3s/k3d auf Customer-Box** | 2-3 Tage | Volle Kontrolle. Kein Olares-Vendor-Lock. Kunde nutzt sein eigenes K8s. | Verliert: One-Click-Install, Authelia-SSO-Integration, Backup-Infrastruktur, Cloudflare-Tunnel-Provisioning. Wir müssen Auth selbst bauen oder weglassen. |
| **C) Demo aus docker-compose lokal** | 0 min (läuft schon) | Sofort sales-ready. Phase 1-3 ist vollständig funktional auf Mac. Pitch „läuft auf Kunden-Box" architekturell weiterhin gültig (alles K8s-native). | Kein Customer-Box-Workflow demonstriert. Phase 4 bleibt offen. |

### Empfehlung

1. **Sofort:** Option C für laufende Sales-Demos sichern. Phase 1-3 lokal ist die Substanz die wir verkaufen.
2. **Parallel diese Woche:** Option A starten — Insilo zu `beclab/apps` PR'en. Vorab Chart-Compliance mit deren Standards verifizieren (vermutlich: weniger restriktive `allowedOutboundPorts`, `runAsUser: true` statt String, evtl. anderen `categories`-Set).
3. **Fallback nach 2 Wochen:** Falls A blockt → Option B als Plan B.

### Was wir bei einem Re-Try der Olares-Route NICHT mehr ausprobieren müssen

- ✅ Helm-Render-Fehler — alle gefixt (v0.1.5 rendert sauber)
- ✅ GPU-Konflikt — Insilo braucht **0** GPU-Slots (Whisper auf CPU, LLM via LiteLLM-Gateway)
- ✅ Cross-App-Provider — `permission.provider` für LiteLLM funktioniert (architektonisch)
- ✅ Init-Chown für hostPath-Mounts — gelöst
- ✅ Redis-Password — gelöst durch Weglassen des `password`-Feldes
- ✅ Image-Pulls — alle 4 Images public auf GHCR und funktionieren

**Der harte Block ist ausschließlich der „Upload"-vs-„Market"-Pfad-Unterschied im Olares-Application-Lifecycle.**

---

## 7d. AUFLÖSUNG der Phase-4-Sackgasse: Custom Market Source (Stand 13. Mai abends)

**Wir hatten den entscheidenden dritten Pfad übersehen.** Marc (aimighty) hat dokumentiert dass Olares **drei** App-Distribution-Pfade kennt, nicht zwei:

| Pfad | Wie | Wann |
|---|---|---|
| **Upload custom chart** | Market UI Upload | Dev-Test nur — bricht für vollwertige Apps (§7c) |
| **beclab/apps PR** | PR an `beclab/apps`, GitBot mergt | Globale Sichtbarkeit, 1-2 Wochen Prozess |
| **Custom Market Source** ⭐ | Eigene Cloudflare-Pages-URL die Olares' Market-API spricht. Olares pollt alle 5 min. | **Private Distribution, voller BFL-Flow, 1-2 Tage** |

### Wie es funktioniert

Marc hat unter `aimighty-market.pages.dev` einen Cloudflare-Pages-Service deployed der vier Olares-Market-API-Endpoints serviert:

```
GET  /api/v1/appstore/hash          → Catalog-Hash für Change-Detection
GET  /api/v1/appstore/info          → Liste aller Apps (Summary)
POST /api/v1/applications/info      → Details für IDs (Batch)
GET  /api/v1/applications/<name>/chart → Helm-Chart als base64-gzip
```

Eine Olares-Box mit dieser URL als Market Source ruft die Endpoints alle 5 min. Wenn der Catalog-Hash sich ändert (= Version bump), zieht Olares die neuen Apps und behandelt sie **wie offizielle Market-Apps** — also: `application` CR wird erstellt, `bytetrade.io/ns-owner` Label gesetzt, `app-np` NetworkPolicy gerendert. Damit löst sich der ganze check-auth-Block von §7c in Luft auf.

### Unser Plan: D1 (Piggyback auf aimighty-market)

Kai hat Schreibzugriff auf das `aimighty-market` Repo (`/Users/marc/Documents/OpenCode/aimighty`). Insilo wird dort als App eingetragen, parallel zu den anderen aimighty-Apps. Das passt strategisch weil Insilo eh über aimighty.de vertrieben wird.

### Workflow für Insilo-Submission an aimighty-market

1. **Insilo-Chart anpassen** (siehe Liste unten)
2. **Chart packen + base64-encoden:**
   ```bash
   helm package olares/ -d /tmp/
   base64 -i /tmp/insilo-0.1.6.tgz | tr -d '\n' | pbcopy
   ```
3. **In aimighty-Repo** (`/Users/marc/Documents/OpenCode/aimighty`):
   - `functions/_apps.ts`: neuen Insilo-Eintrag mit Metadata
   - `functions/_lib.ts`: Insilo's `"insilo-0.1.6.tgz"` Key + base64-String in `CHARTS`-Map
   - Commit + Push (GitHub Auto-Deploy nach Cloudflare Pages)
   - Optional: `wrangler pages deploy` für sofortigen Effekt
4. **Auf Kai's Olares-Box:** Market Source schon konfiguriert (aimighty-market). Insilo erscheint nach ≤ 5 min im Market → Install klicken → vollständiger BFL-Flow → läuft.
5. **Wenn Insilo nicht erscheint:** Market Source entfernen + neu hinzufügen (Olares' Sync-Button leert den Cache nicht zuverlässig)

### Insilo-Chart-Anpassungen die nötig sind

Aus Marc's Doku herausdestilliert für Insilo-spezifischen Adjustment:

| Anpassung | Datei | Begründung |
|---|---|---|
| `entrances[0].name`: `app` → `insilo` | `OlaresManifest.yaml` | Marc's Regel: muss `metadata.name` matchen, sonst „Incompatible with your Olares" |
| `entrances[0].host`: `insilo-frontend` → `insilo` | dito | dito — und dann muss K8s-Service-Name auch `insilo` werden |
| `entrances[0].openMethod: window` ergänzen | dito | sonst zeigt Olares „running" aber Click öffnet nichts |
| Service-Name in `templates/services.yaml` von `insilo-frontend` → `insilo` (für den Frontend-Service) | `templates/services.yaml` | Service-Name muss Entrance-Host matchen |
| Zweite `OlaresManifest.yaml` im Repo-Root | neu | Marc's „Two-Manifest-Pattern" — Root-Manifest für Store-Metadata, Chart-Manifest für Install |
| `values.yaml` auf doppelte `olaresEnv:` Keys prüfen | `values.yaml` | Sonst YAML-Parse-Fehler beim chartrepo sync |
| Version sync 4-fach: `_apps.ts` ↔ `CHARTS` Key ↔ `Chart.yaml` ↔ `OlaresManifest.yaml` | aimighty-Repo + Insilo-Repo | Marc's „Goldene Regel" — diese vier Stellen MÜSSEN identisch sein |

### Was wir bei den Anpassungen behalten (alles richtig aus Phase-4-Marathon)

- ✅ `allowedOutboundPorts: [443]` für HF-Modell-Download
- ✅ `runAsUser: "1000"` als String
- ✅ `middleware.redis.namespace` ohne password-Feld
- ✅ `permission.provider` für LiteLLM Cross-App-Call
- ✅ `appScope.clusterScoped: false`
- ✅ Init-Chown-Container für hostPath-Mounts
- ✅ Worker-Module-Pfad `app.worker:celery_app`
- ✅ 4 Container-Images public auf GHCR

### Realistisches Timing

| Tag | Aktion |
|---|---|
| 1 (heute/morgen, ~4h) | Insilo-Chart-Anpassungen (entrance name/host/openMethod, service-name, two-manifest-pattern), Chart neu packen, lokal lint |
| 2 (~2h) | aimighty-market Repo: `_apps.ts` + `_lib.ts` einfügen, commit, push, CF-Pages-Deploy, Verifikations-curl |
| 2 (~1h) | Auf Kai's Box: Market Source entfernen+neu hinzufügen, Insilo installieren, Pods werden Ready, End-to-End-Test |
| 3 (Optional) | Screenshots + bessere Beschreibungen für Store-Listing aufpolieren, Version bumpen, redeploy |

**Verglichen mit Weg A (beclab/apps PR, 1-2 Wochen) und Weg B (K3s, 2-3 Tage) ist das ein deutlicher Win.**

---

## 7e. Marc's Gold-Standard-Playbook — destillierte Regeln

Marc (aimighty) hat ein detailliertes Playbook gemacht für seinen Custom-Market-Source-Workflow.
Volltext in [`docs/MARKET_SOURCE_PLAYBOOK.md`](MARKET_SOURCE_PLAYBOOK.md). Hier die destillierten
Regeln die wir auf Insilo angewendet haben:

### Golden Rule: Version-Konsistenz an 4 Stellen

Die Version MUSS identisch sein in:

| Stelle | Datei | Feld |
|---|---|---|
| Market Source App-Definition | `aimighty/functions/_apps.ts` | `metadata.version` |
| Chart-Dict Key | `aimighty/functions/_lib.ts` | `"<name>-<version>.tgz"` |
| Helm Chart | `insilo/olares/Chart.yaml` | `version` UND `appVersion` |
| Olares Manifest (BEIDE) | `OlaresManifest.yaml` (root + chart) | `metadata.version` UND `spec.versionName` |

Bei v0.1.7 hatten wir noch `Chart.appVersion: "0.1.0"` und `spec.versionName: '0.1.0'` —
weicht von Marc's Rule ab. **In v0.1.8 alles auf `0.1.8` synchron.** Beim nächsten Bump alle
4 Stellen anfassen.

### Naming-Regeln (Marc's strikte Linie)

| Was | Beispiel Insilo | Warum |
|---|---|---|
| `metadata.name` (App-Name) | `insilo` | lowercase, no hyphens, regex `^[a-z0-9]{1,30}$` |
| `entrance[0].name` | `insilo` | MUSS metadata.name matchen — sonst „Incompatible with your Olares" |
| `entrance[0].host` | `insilo` | MUSS metadata.name matchen — ist der K8s-Service-Name |
| `Service.metadata.name` (in services.yaml) | `insilo` | MUSS entrance host matchen |
| `Deployment.metadata.name` (frontend) | `insilo` | MUSS Service-Name matchen |
| Folder-Name beim Packen | `insilo/` | Chart.yaml.name dictates dies, in unserem Repo aber `olares/` weil wir Helm aus `olares/` packen — der Tarball-Inhalt ist trotzdem `insilo/` (Helm setzt's anhand Chart.name) |

### Entrance-Konfiguration

```yaml
entrances:
- name: insilo                  # MUSS metadata.name matchen
  host: insilo                  # = K8s-Service-Name
  port: 3000
  authLevel: internal           # **internal** (nicht private!) für LAN-friendly UX
  invisible: false
  openMethod: window            # REQUIRED für Apps mit Web-UI, sonst Click → nichts
```

**`authLevel` Unterschiede** (wir hatten v0.1.7 auf `private`, gefixt in v0.1.8):
- `internal` — LAN-Access ohne Authelia, externer Access mit Auth. Empfohlen für User-facing Apps.
- `private` — IMMER Auth (auch LAN). Zu strict für normale Use-Cases.
- `public` — keine Auth (Open Web). Nur für unauthenticated Public-Endpoints.

### Two-Manifest-Pattern

App-Repo braucht **zwei** OlaresManifest.yaml mit **identischen** version + upgradeDescription:
- `<repo-root>/OlaresManifest.yaml` — Store-Metadata (was Olares im Market UI zeigt)
- `<repo-root>/<appname>/OlaresManifest.yaml` — Install-Config (was Olares zum Installieren nutzt)

In unserem Insilo-Repo: root-Manifest + `olares/OlaresManifest.yaml`. Beim Anfassen IMMER beide
gleichzeitig anpassen (oder root als symlink/copy der chart-Version pflegen).

### Cloudflare-Auto-Deploy bewusst AUS

Marc hat Auto-Deploy deaktiviert auf dem `aimighty` CF-Pages-Projekt — sonst kann ein LLM
versehentlich `aimighty.de` Website durch Market-Source-API ersetzen (ist Marc 1x passiert).
**Deploy IMMER manuell:**

```bash
cd ~/Documents/apps/aimighty
npx wrangler login                                                  # einmalig, browser-based
npx wrangler pages deploy functions/ --project-name=aimighty-market
```

Team-Convention: am Ende einer Session zu Claude sagen „release auf market" → Claude führt
den Deploy aus. **Niemals `git push` Auto-Deploy aktivieren.**

### Base64-Hygiene

- **NIE alten Base64-String wiederverwenden** — durch Cloudflare-Encoding kann er korrupt werden
  (HTTP 500 / error 1101). Jedes Mal frisch: `base64 -i <name>-<version>.tgz | tr -d '\n'`.
- Wenn Chart-Download 500 zurückgibt: Chart neu packen, neu base64-encoden, neu deployen.

### Helm-Chart YAML-Gotchas (von Marc gelernt)

- **Doppelte Keys in `values.yaml`** (z.B. `olaresEnv:` zweimal) brechen chartrepo-sync
- **Block-Skalar `|` Indentation**: Alle Zeilen müssen ≥ initial-Einzug haben — sonst bricht YAML-Parser
- **vLLM `--task score` Trap**: `api_server.py` versteht das nicht, nur `vllm serve` CLI. Bei uns irrelevant (kein vLLM).

### Olares-Cache Invalidierung (auf der Box)

Wenn neue Chart-Version nicht erscheint im Market-UI:
- **Sync-Button im Market UI reicht NICHT** — Olares Cache invalidiert nur bei Market-Source-Re-Add
- **Anleitung:** Settings → Market Sources → `aimighty-market.pages.dev` → **Remove** → 5 sec → **Add** wieder

### Häufige Failure-Modes & Fixes

| Fehler | Ursache | Fix |
|---|---|---|
| `Incompatible with your Olares` | entrance.name ≠ metadata.name | beide auf App-Namen setzen |
| App zeigt „running" statt „open" | `openMethod: window` fehlt | zum entrance hinzufügen |
| Chart 404 | CHARTS-Key passt nicht zu `<name>-<version>.tgz` | Key korrigieren |
| Chart 500 (error 1101) | korruptes Base64 | frisch encoden |
| Alte Version trotz Bump | Catalog-Hash unchanged ODER Olares-Cache | Version bumpen ODER Market-Source remove+add |
| envs nicht editierbar in UI | `editable: true` fehlt | in beiden OlaresManifest setzen |
| Build hängt bei chartrepo timeout | chartrepo 3s deadline | Version bumpen → fresh re-fetch |

---

## 7f. Phase-4b-Learnings — vom v0.1.7-Install-Success bis v0.1.12-API-Architektur

Nach dem v0.1.7-Marc-Golden-Rule-Fix lief der Install zum ersten Mal sauber durch
(Custom Market Source Pfad oder simpler Upload-custom-chart Pfad, beide funktionieren
solange das Chart korrekt ist). Die nächsten Iterationen v0.1.8-v0.1.12 haben dann
die Application-Layer-Issues gelöst.

### Issue 1: Frontend-Backend-Kommunikation broken (v0.1.7-v0.1.10)

**Symptom:** PWA lädt sauber, „Besprechungen" überschrift sichtbar, dann
„Verbindung unterbrochen. Backend nicht erreichbar."

**Root Cause #1:** Frontend env var `NEXT_PUBLIC_API_URL` zeigte auf den
api-Entrance (`https://e5d605f31.kaivostudio.olares.de`). Browser-Fetch dorthin
ging durch Authelia → 302 → CORS-Block.

**Lösung-Versuch (v0.1.10):** Next.js Server-Side `rewrites()` proxies
`/api/*` auf interner Cluster-DNS. Browser ruft same-origin → kein CORS.
- `frontend/next.config.mjs`: rewrites() zu `INSILO_BACKEND_INTERNAL`
- `frontend/lib/api/client.ts`: `API_BASE = process.env.NEXT_PUBLIC_API_URL ?? ""`
- `olares/templates/deployment-frontend.yaml`: `NEXT_PUBLIC_API_URL=""` + `INSILO_BACKEND_INTERNAL=http://insilo-backend:8000`

**Root Cause #2 (v0.1.11):** Next.js bakt `NEXT_PUBLIC_*` Vars **zur BUILD-Zeit**
ins JS-Bundle, Runtime-Env überschreibt das nicht. Unser Dockerfile hatte:
```dockerfile
ENV NEXT_PUBLIC_API_URL=https://insilo-api.placeholder/api
```
Das Bundle hatte den Placeholder-URL hardgekodet → Browser versuchte `placeholder.domain` → connection broken.

**Fix:** Dockerfile `ENV NEXT_PUBLIC_API_URL=` (leer) → JS verwendet `API_BASE=""`
→ relative URLs → same-origin → Next.js rewrites greift.

### Issue 2: Backend Envoy returns 401 (v0.1.11 → v0.1.12)

**Symptom:** Nach v0.1.11 Frontend-Fix: PWA lädt, aber API-Calls geben **HTTP 401** zurück.

**Root Cause:** Backend-Pod hat **Envoy-Sidecar** (wegen api-Entrance).
Envoy intercepiert **ALLE TCP-Inbounds** (iptables-Regel `-A PROXY_INBOUND -p tcp -j PROXY_IN_REDIRECT`).
Bei interner Cluster-IP-Traffic ist keine Authelia-Session-Cookie da (Browser-Cookies sind frontend-domain-scoped).
Envoy → Authelia-Check fail → 401.

Verifiziert via `kubectl exec frontend-pod -- curl http://insilo-backend:8000/api/v1/meetings` →
HTTP 401 (mit AND ohne X-Bfl-User-Header, mit AND ohne Pod-IP direkt).

**Fix (v0.1.12):** **api-Entrance komplett aus OlaresManifest entfernen.**
Damit:
- Backend-Pod kriegt KEINEN Envoy-Sidecar (1/1 statt 2/2)
- Internal Service-Calls gehen direkt zur FastAPI
- Next.js Server-Proxy ruft `http://insilo-backend:8000` ohne Auth-Hop
- Frontend-Envoy injiziert X-Bfl-User auf Browser-Request → Next.js rewrites forwarded
- Backend FastAPI bekommt X-Bfl-User → user identification works

### Issue 3: Helm-Upgrade outside Olares Market funktioniert, aber Tracking-State

**Was wir gemacht haben:** Helm-Upgrades direkt via SSH (`helm upgrade insilo /tmp/...tgz`)
um Iterationszyklen zu beschleunigen (statt Market UI Upload für jede Version).

**Funktioniert technisch:** Pods werden neu deployed mit neuen Images, ApplicationManager bleibt `running`.

**Achtung:** Olares Market UI zeigt weiter die alte Version-Nummer (z.B. v0.1.9) obwohl
Helm v0.1.11 deployed hat — cosmetisches Issue. Olares Market DB trackt Versionen
separat von Helm-Releases.

**Empfehlung:** Für saubere Sync den vollen Cycle via UI: Uninstall → Upload neue Version → Install.
Für schnelle Iteration: helm upgrade. Nach mehreren Helm-Upgrades irgendwann uninstall+reinstall
um Markt-State zu syncen.

### Issue 4: Chart-Version vs Image-Tag Trennung

Bei v0.1.12 (only manifest change) haben wir Chart-Version gebumpet aber **Image-Tags
auf 0.1.11 gelassen** (weil keine Code-Änderung, kein Image-Rebuild nötig).

**Regel:** Chart-Version bumpt IMMER bei Manifest-Änderung (Marc's Golden Rule).
Image-Tags bumpen NUR bei Code-Änderung (sonst unnötige GH-Actions-Builds).

### Issue 5: SSH-Zugang ist Gold

`ssh olares@192.168.112.125` mit `~/.ssh/id_ed25519` Key (etabliert in dieser Session).
Ermöglicht:
- Direkte kubectl-Calls auf der Box
- helm upgrade ohne Market-UI
- scp Charts zur Box
- Realtime Log-Tails ohne Box-Terminal

**Aber:** Sandbox-Classifier blockt destruktive Aktionen ohne explizite User-Autorisierung
(z.B. Helm-Upgrade, DB-Polling). Bei Bedarf User um `ja, mach` bitten.

### Aktueller Stand & Next Actions (für neue Session)

**Box-State (live verifiziert, 13. Mai abends):**
- Insilo v0.1.12: **running**
- ApplicationManager state: `running`
- `insilo` frontend Pod: **2/2 Ready** (mit Envoy-Sidecar)
- `insilo-backend` Pod: **1/1 Ready** ← KEIN Envoy mehr (api-Entrance entfernt → keine Sidecar-Injection)
- Andere Pods: insilo-embeddings, insilo-whisper, insilo-worker alle 1/1 Running

**Stand 13. Mai abends — funktionierende Pfade ABGENOMMEN:**
1. ✅ DB-Migrationen (11 Tabellen + 4 System-Templates aus seed.sql)
2. ✅ Backend API `/api/v1/meetings` → `200 []`
3. ✅ PWA-Frontend lädt komplett: Aufnahme-Screen + Template-Picker zeigt alle 4 DB-Templates
4. ✅ Mikrofon-Recording funktioniert (Browser-MediaRecorder)
5. ❌ **Audio-Upload kracht (HTTP 500): MinIO nicht erreichbar**

**Phase-4c open issue — Storage-Backend:**

Backend versucht `http://localhost:9000` (lokales MinIO aus docker-compose Dev) für Audio-Upload. Olares hat MinIO unter `tapr-s3-svc.os-platform:4568`, aber:
- **NetworkPolicy** blockt Cross-Namespace zu `os-platform` (TCP-Timeout aus Backend-Pod)
- Olares verwendet **kein Standard-`middleware.minio:`-Pattern** (keine bekannte App nutzt es)
- Credentials für `tapr-s3-svc` sind in Secrets versteckt, undokumentiert

**Pragmatischer Fix für nächste Session — Local-Filesystem Storage:**

Code-Änderung an `backend/app/storage.py`:
- Neue Klasse `LocalStorage` neben `S3Storage`
- Schreibt Audio nach `/app/data/audio/<meeting_id>/<file_id>.webm` (hostPath, schon gemounted)
- Konfig-Schalter: `storage_backend: str = "minio" | "local"` in `config.py`
- In Olares-Deployment: `STORAGE_BACKEND=local` env var setzen

Vorteile:
- Audio bleibt auf der Box (= Datensouveränität-Pitch wörtlich)
- Kein S3-Auth-Hassle
- `/app/data` persistiert über Pod-Restarts (hostPath survives)
- Backup-Strategie: Velero/restic auf `/olares/rootfs/userspace/pvc-userspace-kaivostudio-*/Data/insilo/`

Aufwand: ~30 min Code + Test, ~5 min Image-Build (GH Actions), Chart-Bump auf v0.1.13.

Nach diesem Fix dann End-to-End-Test:
- Aufnahme → Upload → S3-Key in DB → Worker triggert Whisper → Transkript erscheint → LLM-Summary → /ask

**Alternativ (langer Weg):** Olares-Sourcecode lesen wie `tapr-s3-svc` Auth funktioniert + `middleware.minio:` reverse-engineeren. Vermutlich 1-2 Tage Arbeit.

**Wie DB-Migrationen eingespielt wurden** (für Doku falls Box mal neu aufgesetzt wird):
```bash
# Migrations + seed auf Box bringen
scp supabase/migrations/0001_initial_schema.sql supabase/migrations/0002_rls_policies.sql supabase/seed.sql olares@192.168.112.125:/tmp/

# In Backend-Pod kopieren + ausführen
ssh olares@192.168.112.125 "BPOD=\$(kubectl get pod -n insilo-kaivostudio -l component=backend -o jsonpath='{.items[0].metadata.name}'); for f in 0001_initial_schema.sql 0002_rls_policies.sql seed.sql; do kubectl cp /tmp/\$f insilo-kaivostudio/\$BPOD:/tmp/\$f -c backend; done; kubectl exec -n insilo-kaivostudio \$BPOD -c backend -- python3 -c 'import asyncio,asyncpg,os; async def m():
 c=await asyncpg.connect(host=os.environ[\"DB_HOST\"],port=int(os.environ[\"DB_PORT\"]),user=os.environ[\"DB_USER\"],password=os.environ[\"DB_PASSWORD\"],database=os.environ[\"DB_NAME\"])
 for f in [\"/tmp/0001_initial_schema.sql\",\"/tmp/0002_rls_policies.sql\",\"/tmp/seed.sql\"]:
  await c.execute(open(f).read())
asyncio.run(m())'"
```

Ein Init-Container im Chart wäre eleganter — Phase-4b-Item.

**Mac-State:**
- `~/Downloads/insilo-0.1.12.tgz` bereit
- All commits gepusht (ska1walker/insilo + bayerhazard/aimighty)
- aimighty-market.pages.dev hat v0.1.12 in `_apps.ts`+`_lib.ts` **lokal** (aber **NIE deployed via wrangler** — Marc muss noch deployen)
- GitHub Release v0.1.0 hat alle .tgz Assets v0.1.0 bis v0.1.12

**Erste Action neuer Session:**
1. User uploadet `~/Downloads/insilo-0.1.12.tgz` via Olares Market UI → Upload custom chart
2. Watch: `ssh -t olares@192.168.112.125 'watch -n 2 "kubectl get pods -n insilo-kaivostudio"'`
3. Expectation: 5 Pods Ready, backend ist **1/1 nicht 2/2** (kein Envoy)
4. Service Worker im Browser leeren (DevTools → Application → Clear site data)
5. PWA öffnen, „Besprechungen"-Liste sollte laden (oder DB-Migration-Error wenn Tabellen fehlen)
6. End-to-End-Test: Aufnahme → Whisper → Summary → /ask

**DB-Migrationen** sind potentiell offen — kein Init-Container im Chart. Falls Backend
„relation does not exist" Errors wirft: psql aus dem Backend-Pod, `0001_initial_schema.sql`
und `0002_rls_policies.sql` aus `supabase/migrations/` einspielen.

---

## 7b. LLM-Architektur — wie Insilo das Sprachmodell aufruft

**Entscheidung (Commit `a446273`):** Kein eigenes Ollama im Chart. Statt dessen Cross-App-Call zur LiteLLM-App des Olares-Users.

**Vorteile:**
- 4 GB Ollama-Image entfällt aus dem Pull
- 0 GPU-Slot-Reservierung in Insilo
- LLM-Pool für alle kaivo.studio-Apps des Users teilbar
- Kunde kann sein eigenes bevorzugtes LLM in LiteLLM konfigurieren

**API-Pattern (im Code, Datei `backend/app/tasks/summarize.py` + `routers/search.py`):**

```python
# settings: llm_base_url, llm_api_key, llm_model
async with httpx.AsyncClient(timeout=...) as client:
    resp = await client.post(
        f"{settings.llm_base_url}/chat/completions",       # OpenAI-format
        json={
            "model": settings.llm_model,
            "messages": [...],
            "response_format": {"type": "json_object"},    # für summarize
            "temperature": 0.2,
        },
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
    )
    content = resp.json()["choices"][0]["message"]["content"]
```

**Konfiguration:**

| Umgebung | LLM_BASE_URL | LLM_API_KEY | LLM_MODEL |
|---|---|---|---|
| Lokal Mac | `http://localhost:11434/v1` (Ollama nativ) | `sk-local` (Ollama ignoriert) | `qwen2.5:7b-instruct` |
| Olares (via Helm) | `http://litellm-svc.litellm-{{ bfl.username }}.svc.cluster.local/v1` | `sk-1234` (LITELLM_MASTER_KEY der App) | `qwen36a3bvisionone` |

**OlaresManifest-Provider-Declaration** (`olares/OlaresManifest.yaml`):

```yaml
permission:
  appData: true
  appCache: true
  provider:
    - appName: litellm
      providerName: api
      podSelectors:
        - matchLabels:
            io.kompose.service: litellm
```

Falls Olares-Linter diesen Block ablehnt: `providerName` muss möglicherweise dem Wert entsprechen, den die LiteLLM-App in ihrem eigenen `provider:`-Block deklariert hat. Aktuell raten wir `api`. Echter Provider-Name muss aus LiteLLM-Manifest gelesen werden (im `chartrepo/v2/.../litellm-X.X.X/OlaresManifest.yaml` auf der Box).

---

## 8. Wichtige IDs & URLs

- **GitHub-Repo:** https://github.com/ska1walker/insilo (public)
- **GitHub-Release v0.1.0:** https://github.com/ska1walker/insilo/releases/tag/v0.1.0
- **Aktueller Chart-Stand:** Lokal `dist/insilo-0.1.5.tgz` (~34 KB, gitignored). Auf GitHub-Release v0.1.0 als Asset (insilo-0.1.0.tgz bis insilo-0.1.5.tgz nebeneinander). Commits zu den Chart-Iterationen Mai 13. evtl. noch ungepusht — `git status` checken.
- **GHCR-Packages (alle public, linux/amd64):**
  - `ghcr.io/ska1walker/insilo-frontend:0.1.0` (~70 MB)
  - `ghcr.io/ska1walker/insilo-backend:0.1.0` (~130 MB) — gleiches Image für Worker
  - `ghcr.io/ska1walker/insilo-whisper:0.1.0` (~350 MB, faster-whisper)
  - `ghcr.io/ska1walker/insilo-embeddings:0.1.0` (~420 MB, sentence-transformers CPU)
- **Ollama-Image entfernt** seit Commit `a446273` — LLM kommt jetzt von der LiteLLM-Olares-App des Users.
- **Olares-Box-User:** `kaivostudio @ olares.de`
- **GPU:** NVIDIA RTX 5090 Laptop · 24 GB VRAM · Time-slicing aktiv · Alle Slots an andere Apps vergeben → Insilo bewusst GPU-frei
- **LiteLLM-Master-Key:** `sk-1234` (Default der Olares-LiteLLM-App, in deren env als `LITELLM_MASTER_KEY` zu finden)
- **LiteLLM-Modell-Name:** `qwen36a3bvisionone` (= der Service-Name der Qwen-Vision-Olares-App; LiteLLM mappt das auf intern)
- **Olares-Spec:** v0.11.0 ([docs](https://docs.olares.com/developer/develop/package/manifest.html))

---

## 9. Phase-4-Status & Next-Steps (Stand 13. Mai 2026 — strategische Neuausrichtung)

### Was bereits abgeschlossen ist

- [x] Container-Images bauen + pushen (GHCR public, linux/amd64)
- [x] Helm-Chart paketieren + als GitHub-Release-Asset (aktuell v0.1.5)
- [x] Embeddings-CUDA-Bloat fixen (2.8 GB → 420 MB)
- [x] Repo public schalten (Icon-Fix)
- [x] Helm-Template-Render-Fehler `redis.namespaces.insilo` → `redis.namespace`
- [x] GPU-Konflikt gelöst: 0 GPU-Slots durch CPU-Whisper + LiteLLM-Gateway-Cross-Call
- [x] Worker-Module-Name fixen: `app.workers.celery_app` → `app.worker:celery_app`
- [x] Init-Chown-Container für hostPath-Mounts (Whisper, Embeddings, Backend, Worker)
- [x] Redis-Password-Fix: `middleware.redis.password: auto` entfernt
- [x] Chart-Version-Sync: `Chart.yaml.version` ↔ `OlaresManifest.metadata.version`
- [x] `appScope.clusterScoped: false` deklariert (kein Effekt, aber Manifest-best-practice)
- [x] **Olares-Sackgasse identifiziert + dokumentiert** in §7c

### Plan: D1 — Custom Market Source via aimighty-market (Stand v0.1.8, 13. Mai abends)

Siehe §7d für Architektur, §7e für Marc's Gold-Standard-Playbook-Regeln. Action-State:

#### Insilo-Chart auf v0.1.8 — ✅ DONE
- [x] entrance name+host = `insilo` (matched metadata.name)
- [x] `openMethod: window` gesetzt
- [x] Service.metadata.name + Deployment.metadata.name (frontend) = `insilo`
- [x] Root + Chart OlaresManifest synced (Two-Manifest-Pattern)
- [x] `values.yaml` ohne doppelte `olaresEnv`-Keys
- [x] Version-Sync (Marc's Golden Rule) auf 0.1.8 in **allen 4** Stellen: Chart.version, Chart.appVersion, manifest.metadata.version, manifest.spec.versionName
- [x] `authLevel: internal` (statt private — LAN-friendly, matches Marc's aimighty-apps)
- [x] Lint + package: `dist/insilo-0.1.8.tgz` (34.7 KB)
- [x] GitHub-Push: `ska1walker/insilo` HEAD = chart v0.1.8

#### aimighty-market eingetragen — ✅ DONE
- [x] base64 vom v0.1.8 Chart (46.2 KB) generiert
- [x] `aimighty/functions/_apps.ts`: Insilo-Eintrag mit Metadata + `authLevel: internal`
- [x] `aimighty/functions/_lib.ts`: `"insilo-0.1.8.tgz"` Key + base64-String in CHARTS-Map
- [x] TypeScript-Sanity: keine **neuen** Errors (5 pre-existing in Marc's envs-Block)
- [x] Commit + Push auf `bayerhazard/aimighty` main

#### Cloudflare-Pages Deploy — ⏸ wartet auf Auth
- [ ] `npx wrangler login` (Browser-basiert, einmalig — Marc muss Kai vorher zum CF-Team einladen)
- [ ] `npx wrangler pages deploy functions/ --project-name=aimighty-market`
- [ ] Verify: `curl https://aimighty-market.pages.dev/api/v1/appstore/info` zeigt insilo
- [ ] Verify: `curl -o /dev/null -w "%{http_code}\n" https://aimighty-market.pages.dev/api/v1/applications/insilo/chart` = 200

#### Auf Olares-Box installieren — ⏸ nach Deploy
- [ ] SSH-Zugang verifiziert: `ssh olares@192.168.112.125 "kubectl get nodes"` ✅
- [ ] Market Source `aimighty-market.pages.dev` ist als Source konfiguriert (Marc's Doku: in Olares Market → Settings → Market Sources)
- [ ] **Sync-Force:** Source entfernen + neu hinzufügen (Cache-Invalidierung)
- [ ] Bis zu 5 Min warten bis Insilo im Market erscheint
- [ ] Install klicken → Olares Pipeline läuft

#### Verification bei laufender Installation
- [ ] `application.app.bytetrade.io/insilo-kaivostudio-insilo` wird erstellt (vorher nie passiert)
- [ ] `kubectl get ns insilo-kaivostudio -o jsonpath='{.metadata.labels}'` → `bytetrade.io/ns-owner: kaivostudio` automatisch da
- [ ] `kubectl get networkpolicy -n insilo-kaivostudio` → `app-np` (nicht mehr `others-np`)
- [ ] Alle 5 Pods werden Ready, frontend hat „Open"-Button
- [ ] Click → PWA öffnet sich im Browser-Tab

#### End-to-End Test
- [ ] 30-sec Test-Aufnahme via PWA → Whisper transkribiert → LiteLLM-Summary erscheint
- [ ] `/ask` funktioniert
- [ ] DB-Migrationen aus dem Backend-Pod manuell einspielen (Init-Container wäre Phase 4b)

### Bewusst nicht jetzt: andere Wege

- **beclab/apps PR (vorheriger „Weg A")** — nicht nötig, D1 ist schneller und behält Distribution-Hoheit. Falls Insilo global verfügbar werden soll: später.
- **K3s („Weg B")** — bleibt Fallback wenn aimighty-market irgendwann nicht mehr passt.
- **Lokal docker-compose („Weg C")** — bleibt für Sales-Demos diese Woche, parallel zum D1-Setup.

### Was im Falle des Re-Try NICHT mehr nötig ist

Alle technischen Hürden außer der „Upload-vs-Market"-Klassifizierung sind gelöst. Bei D1-Submission starten wir effektiv von v0.1.6 mit allen Fixes drin. Der ska1walker/apps Fork mit der vorbereiteten beclab/apps-Submission kann liegen bleiben — falls wir später doch Market-PR machen wollen ist die Vorarbeit da.

---

## 10. Phase 4 abgeschlossen — was kommt danach

**Phase 4b — Olares-Paketierung-Polish** (nach erfolgreichem Erst-Install):
- Init-Container für DB-Migrationen + Model-Pulls
- App-Update-Flow testen (chart v0.1.1, dann install)
- GPU-Sharing zwischen Whisper + Ollama + Embeddings (Time-Slicing schon aktiv)
- Backup-Integration (Velero auf Olares)

**Phase 4c — Provider-Pattern für Multi-App** (wenn 2. App in Sicht):
- `provider`-Block im OlaresManifest aktivieren
- `/api/v1/meetings` als read-only Provider exposen
- CallList o.ä. als Konsument testen

**Phase 5 — Pilot-Deployment** (Q1 2027 laut ROADMAP):
- Erstkunde via aimighty finden
- Vorbereitete Olares One als Leihgerät
- 30-Tage-Hyper-Care
- Feedback → Phase 6

**Bewusst geschoben:**
- **Live-Transkription via WebSocket** (Phase 3b) — Polling reicht für MVP, WS-Streaming-Aufwand groß
- **Speaker Diarization** (Phase 2b, pyannote) — auf Mac CPU zu langsam für Dev, macht erst auf Olares-GPU Sinn

---

## 11. Tipps für eine neue Claude-Session

1. **Lies CLAUDE.md erst** — komplette Architektur in einem File.
2. **Lies docs/HANDOFF.md** (diese Datei) — Status + Learnings + Debug-Cheatsheet.
3. **Phase 4 ist BLOCKED auf Upload-Pfad** — siehe §7c. Vor weiteren Olares-Versuchen lesen, sonst läufst du in 10h die selben Sackgassen wie wir.
4. **`git log --oneline -20`** zeigt die Phasen-Commits, jeder ist groß und thematisch klar (chronologisch absteigend: phase 3 → phase 2 → phase 1 → bundle pivot → initial scaffold).
5. **Bei UI-Arbeit:** Skills `frontend-design` + `UI/UX Pro Max` aktivieren. Designsystem strikt aus [`docs/DESIGN.md`](DESIGN.md).
6. **Bei Olares-Chart-Arbeit:** vor jedem Change `helm lint olares/ -f olares/values-olares-stub.yaml`, dann `helm package olares/ -d dist/`. Chart.yaml.version UND OlaresManifest.metadata.version IMMER synchron bumpen. Bei Bundle-Annahmen-Änderungen über `.Values.<x>.<y>`: auf Box per `kubectl logs -n os-framework app-service-0` verifizieren.
7. **Bei Backend-Änderungen:** keine Auth-Logik bauen. User-Identität ist via `X-Bfl-User` Header. Lokal mit `NEXT_PUBLIC_USER=devuser` mocken.
8. **Bei DB-Schema-Änderungen:** neue Migration in `supabase/migrations/0003_*.sql` anlegen, dann `psql` einspielen.
9. **Sprachregel:** UI deutsch Sie-Form, Code/Commits englisch.
10. **Olares-Debug:** „download failed" sagt nichts aus. Immer in `kubectl logs -n os-framework app-service-0` schauen — dort steht der echte Render/Validate/Pull-Fehler. Siehe §7a (Debug-Cheatsheet).
11. **Wenn jemand Phase 4 retry'en will:** zuerst §7c (Sackgassen-Analyse) UND §7f (Phase-4b-Learnings) lesen. Phase 4 ist effektiv gelöst — `~/Downloads/insilo-0.1.12.tgz` ist installierbar via "Upload custom chart" in Market UI.

12. **SSH-Zugang zur Box:** `ssh olares@192.168.112.125` ist eingerichtet (id_ed25519 Key). Für jeden kubectl/helm Befehl auf der Box. Sandbox blockt destruktive Aktionen ohne explizite User-Autorisierung.

13. **Auto-Deploy ist AUS auf aimighty CF-Pages** (Marc's bewusste Entscheidung — siehe `docs/MARKET_SOURCE_PLAYBOOK.md`). Nach Code-Änderung im `bayerhazard/aimighty` Repo IMMER manuell `wrangler pages deploy functions/ --project-name=aimighty-market` ausführen. Marc oder Kai (mit CF-Team-Membership) macht das.

14. **NEXT_PUBLIC_API_URL ist build-time gebakt, nicht runtime.** Im Dockerfile leer setzen damit JS-Bundle relative URLs nutzt. Dann Next.js rewrites() den /api/* Pfad zum Backend proxien lassen.

15. **Backend-Pods mit Envoy-Sidecar bouncen ALLE TCP-Inbounds via Authelia.** Wenn man Internal-API-Calls von Frontend→Backend braucht ohne Auth-Hop: api-Entrance entfernen (= kein Envoy auf Backend). Frontend-Envoy bleibt + injiziert X-Bfl-User, Next.js Server-Proxy forwarded das.

---

*Letzte Aktualisierung: 13. Mai 2026 (Abend) — v0.1.12 ready für End-to-End-Test. §7c, §7d, §7e, §7f decken den kompletten Phase-4-Verlauf ab. Commit-SHA dieses Stands: siehe `git log`.*
