# Handoff — Stand & Learnings (Mai 2026)

> Dieses Dokument bringt eine neue Claude-Session (oder einen frischen Mitarbeiter)
> in **<2 Minuten** auf den Stand. Kein Marketing, nur Substanz.

---

## 1. Wo wir gerade stehen

| Phase | Status | Lokal | Auf Olares |
|---|---|---|---|
| **1 — Audio-Pipeline** (Aufnahme → Whisper-Transkript) | ✅ live | ✅ läuft | 🟡 chart deployed, scheduling tbd |
| **2 — LLM-Summary** (Qwen + 4 System-Templates) | ✅ live | ✅ läuft | 🟡 via LiteLLM-Gateway konfiguriert |
| **3 — RAG / „Ask"** (BGE-M3 + pgvector + grounded answers) | ✅ live | ✅ läuft | 🟡 wartet auf Schedule |
| **4 — Olares-Paketierung** | 🟡 5. Install-Versuch | n/a | **Whisper jetzt CPU, kein GPU-Slot mehr** |
| 5 — Pilot-Deployment | not started | | |

**Letzter konkreter Stand (Commit `363e2e9`):**
- 4 Container-Images public auf `ghcr.io/ska1walker/insilo-*:0.1.0` (linux/amd64). Ollama-Image **entfernt** — wir nutzen LiteLLM stattdessen.
- Helm-Chart `dist/insilo-0.1.0.tgz` als GitHub-Release-Asset (8.3 KB).
- Insilo braucht **0 GPU-Slots** auf der Box. Whisper auf CPU (5× langsamer aber unproblematisch).
- LLM-Calls gehen an `http://litellm-svc.litellm-{{ .Values.bfl.username }}.svc.cluster.local/v1` — die schon-installierte LiteLLM-App des Users serviert das Modell `qwen36a3bvisionone`.
- `OlaresManifest.permission.provider` deklariert Cross-App-Zugriff auf LiteLLM (Format: `{appName, providerName, podSelectors}`).
- Repo `ska1walker/insilo` ist **public** (war privat → Icon-404 → erste downloadFailed-Welle).

**Aktuelle Aufgabe:** User soll die alte Insilo-App in Olares Studio deinstallieren (war auf state=`stopped`, Reason=`Unschedulable` wegen GPU-Konflikt vor Whisper-CPU-Fix), dann neues `.tgz` hochladen.

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
- **Aktueller Chart-Stand:** Commit `363e2e9` (Whisper-CPU). Lokal: `dist/insilo-0.1.0.tgz` (8.3 KB, gitignored). Auf Release als Asset.
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

## 9. Phase-4-Next-Steps

- [x] Container-Images bauen + pushen (GHCR public, linux/amd64)
- [x] Helm-Chart paketieren + als GitHub-Release-Asset
- [x] Embeddings-CUDA-Bloat fixen (2.8 GB → 420 MB, Commit Phase-1c)
- [x] Repo public schalten (Icon-Fix)
- [x] Helm-Template-Render-Fehler `redis.namespaces.insilo` → `redis.namespace` (Commit `d38877e`)
- [x] **GPU-Konflikt gelöst:** Ollama-Deployment komplett aus dem Chart (`a446273`), LiteLLM-Gateway als Cross-App-Provider (`a446273` + `b12ed69`), Whisper auf CPU (`363e2e9`). Insilo braucht jetzt **0 GPU-Slots**.
- [ ] **5. Install-Versuch in Olares Studio durchziehen** — User soll alte App deinstallieren, neues `.tgz` (Stand `363e2e9`) hochladen. Erwartung: keine Unschedulable mehr, Pods kommen hoch.
- [ ] Verify: LiteLLM-Call vom Insilo-Backend-Pod aus geht durch. `kubectl logs -n insilo-kaivostudio deployment/insilo-backend | grep -i litellm` nach erster Aufnahme.
- [ ] DB-Migrationen auf der Box ausführen — **kein Init-Container im Chart**. Aktuell muss `psql` manuell aus dem Backend-Pod oder via `kubectl exec` laufen.
- [ ] Erste End-to-End-Aufnahme: Mikro → Whisper (CPU) → LiteLLM/Qwen-Vision → Summary → /ask.
- [ ] Falls bestätigt: HANDOFF.md updaten + Phase 4 schließen.

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
3. **`git log --oneline -20`** zeigt die Phasen-Commits, jeder ist groß und thematisch klar (chronologisch absteigend: phase 3 → phase 2 → phase 1 → bundle pivot → initial scaffold).
4. **Bei UI-Arbeit:** Skills `frontend-design` + `UI/UX Pro Max` aktivieren. Designsystem strikt aus [`docs/DESIGN.md`](DESIGN.md).
5. **Bei Olares-Chart-Arbeit:** vor jedem Change `helm lint olares/ -f olares/values-olares-stub.yaml` laufen lassen, dann `helm package olares/ -d dist/`. **Wenn du Bundle-Annahmen über `.Values.<x>.<y>` änderst, im Zweifel auf der Olares-Box per `kubectl logs -n os-framework app-service-0` verifizieren** — die Bundle-Templates hatten mehrere falsche Annahmen über die genaue Form der Olares-injected values.
6. **Bei Backend-Änderungen:** keine Auth-Logik bauen. User-Identität ist via `X-Bfl-User` Header. Lokal mit `NEXT_PUBLIC_USER=devuser` mocken.
7. **Bei DB-Schema-Änderungen:** neue Migration in `supabase/migrations/0003_*.sql` anlegen, dann `psql` einspielen.
8. **Sprachregel:** UI deutsch Sie-Form, Code/Commits englisch.
9. **Olares-Debug:** „download failed" sagt nichts aus. Immer in `kubectl logs -n os-framework app-service-0` schauen — dort steht der echte Render/Validate/Pull-Fehler. Siehe Sektion 7a (Debug-Cheatsheet).

---

*Letzte Aktualisierung: Mai 2026, mid-Phase-4 (Olares-Install retry nach Icon-Fix). Commit-SHA dieses Stands: siehe `git log`.*
