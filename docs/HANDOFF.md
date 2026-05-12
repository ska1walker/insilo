# Handoff — Stand & Learnings (Mai 2026)

> Dieses Dokument bringt eine neue Claude-Session (oder einen frischen Mitarbeiter)
> in **<2 Minuten** auf den Stand. Kein Marketing, nur Substanz.

---

## 1. Wo wir gerade stehen

| Phase | Status | Lokal | Auf Olares |
|---|---|---|---|
| **1 — Audio-Pipeline** (Aufnahme → Whisper-Transkript) | ✅ live | ✅ läuft | offen |
| **2 — LLM-Summary** (Qwen 2.5 + 4 System-Templates) | ✅ live | ✅ läuft | offen |
| **3 — RAG / „Ask"** (BGE-M3 + pgvector + grounded answers) | ✅ live | ✅ läuft | offen |
| **4 — Olares-Paketierung** | 🟡 mid-flight | n/a | **Install läuft gerade, 3. Versuch** |
| 5 — Pilot-Deployment | not started | | |

**Letzter konkreter Stand:**
- Container-Images für linux/amd64 auf `ghcr.io/ska1walker/insilo-*:0.1.0` — alle 4 **public**
- Helm-Chart `dist/insilo-0.1.0.tgz` (auch als GitHub-Release-Asset)
- `ollama/ollama:latest` als 5. Image, kommt direkt von Docker Hub
- Repo `ska1walker/insilo` ist jetzt **public** (war privat → Icon-404 → `downloadFailed`)
- User soll die App in Olares Studio jetzt neu installieren — Pre-Install-Check sollte durchlaufen

**Größter offener Stolperstein:** `ollama/ollama:latest` ist 4 GB. Falls Install jetzt am Ollama-Pull scheitert, müssen wir das Image auf eine ältere/schlankere Version pinnen.

---

## 2. Architektur in 30 Sekunden

**Insilo** = datensouveräne Meeting-Intelligenz-PWA für deutschen Mittelstand.
**Plattform** = Olares OS (K8s-basiert) beim Kunden. Olares stellt System-Middlewares (PostgreSQL, KVRocks, MinIO, Authelia+Envoy) — wir bauen die nicht selbst.

```
PWA (Next.js) → Backend (FastAPI, X-Bfl-User-Auth via Envoy)
                  ↓ Celery
                  ↓ KVRocks (Redis-API) als Broker
                  ↓
  ┌───────────────┼──────────────┐
  ↓               ↓              ↓
Whisper-Svc   Ollama-Svc   Embeddings-Svc
(faster-whisper) (Qwen 14B)  (BGE-M3)
  ↓               ↓              ↓
        Postgres + pgvector + MinIO
        (Olares-System-Middlewares)
```

**Auth:** Kein eigener Code. Envoy-Sidecar vor jedem Pod prüft Authelia-Token, injiziert `X-Bfl-User` Header. Lokal mocken wir den Header.

**DB:** asyncpg + SQLAlchemy 2.x (kein Supabase-Client mehr). Schema in `supabase/migrations/` (Ordnername historisch, nichts mit Supabase zu tun).

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

---

## 8. Wichtige IDs & URLs

- **GitHub-Repo:** https://github.com/ska1walker/insilo (jetzt public)
- **GitHub-Release v0.1.0:** https://github.com/ska1walker/insilo/releases/tag/v0.1.0
- **GHCR-Packages (alle public, linux/amd64):**
  - `ghcr.io/ska1walker/insilo-frontend:0.1.0` (~70 MB)
  - `ghcr.io/ska1walker/insilo-backend:0.1.0` (~130 MB) — gleiches Image für Worker
  - `ghcr.io/ska1walker/insilo-whisper:0.1.0` (~350 MB, faster-whisper)
  - `ghcr.io/ska1walker/insilo-embeddings:0.1.0` (~420 MB, sentence-transformers CPU)
- **5. Image** (extern): `ollama/ollama:latest` (~4 GB)
- **Olares-Box-User:** `kaivostudio @ olares.de`
- **GPU:** NVIDIA RTX 5090 Laptop · 24 GB VRAM · Time-slicing aktiv
- **Olares-Spec:** v0.11.0 ([docs](https://docs.olares.com/developer/develop/package/manifest.html))

---

## 9. Phase-4-Next-Steps

- [x] Container-Images bauen + pushen (GHCR public, linux/amd64)
- [x] Helm-Chart paketieren + als GitHub-Release-Asset
- [x] Embeddings-CUDA-Bloat fixen
- [x] Repo public schalten (Icon-Fix)
- [ ] **Olares-Install final durchlaufen** (Stand: 3. Versuch nach Icon-Fix)
- [ ] Falls Ollama-4-GB-Pull-Timeout: `ollama/ollama` pinnen auf älteres Tag oder Olares' bereits installierte Ollama-App teilen
- [ ] DB-Migrationen auf der Box ausführen (kein Init-Container im Chart — Hotfix nötig)
- [ ] Erste End-to-End-Aufnahme auf der Box: Mikro → Whisper → Qwen → /ask
- [ ] Whisper-Modell von `tiny` auf `large-v3` umstellen (lokal hatten wir tiny für Dev-Geschwindigkeit; Olares hat GPU)
- [ ] Qwen-Modell ergänzen: das Helm-values setzt `qwen2.5:14b-instruct-q4_K_M`, muss aber von Ollama-Container nach Start gepullt werden — gibt's einen Init-Mechanismus?

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
2. **Lies docs/HANDOFF.md** (diese Datei) — Status + Learnings.
3. **`git log --oneline -20`** zeigt die Phasen-Commits, jeder ist groß und thematisch klar (chronologisch absteigend: phase 3 → phase 2 → phase 1 → bundle pivot → initial scaffold).
4. **Bei UI-Arbeit:** Skills `frontend-design` + `UI/UX Pro Max` aktivieren. Designsystem strikt aus [`docs/DESIGN.md`](DESIGN.md).
5. **Bei Olares-Chart-Arbeit:** vor jedem Change `helm lint olares/ -f olares/values-olares-stub.yaml` laufen lassen, dann `helm package olares/ -d dist/`.
6. **Bei Backend-Änderungen:** keine Auth-Logik bauen. User-Identität ist via `X-Bfl-User` Header. Lokal mit `NEXT_PUBLIC_USER=devuser` mocken.
7. **Bei DB-Schema-Änderungen:** neue Migration in `supabase/migrations/0003_*.sql` anlegen, dann `psql` einspielen.
8. **Sprachregel:** UI deutsch Sie-Form, Code/Commits englisch.

---

*Letzte Aktualisierung: Mai 2026, mid-Phase-4 (Olares-Install retry nach Icon-Fix). Commit-SHA dieses Stands: siehe `git log`.*
