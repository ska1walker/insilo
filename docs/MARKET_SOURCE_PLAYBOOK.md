# Olares Custom Market Source — Deployment Instructions (Gold Standard)

> **Quelle:** Marc (aimighty), aimighty-market.pages.dev maintainer.
> **Verschoben hierher:** 13. Mai 2026 als interne Team-Referenz für Insilo's Distribution via Custom Market Source.
>
> Diese Doku ist 1:1 von Marc übernommen und beschreibt den **bewährten** Workflow für eigene Olares Market Sources auf Cloudflare Pages. Marc's eigene Pfade (z.B. `/Users/marc/Documents/OpenCode/aimighty`) und Beispiel-App-Namen (`aimembqwen3vino`, `aimrerqwen3vllm`) bleiben aus Authentizitäts-Gründen drin.
>
> Für den Insilo-spezifischen Implementierungsplan siehe **HANDOFF.md §7d**. Für die Architektur-Übersicht (warum Custom Market Source der dritte Olares-Distribution-Pfad ist) siehe **OLARES_DEEP_DIVE.md §4**.

---

## Overview

This document describes how to set up, maintain, and deploy apps to a **custom Olares Market Source** hosted on **Cloudflare Pages**. The market source serves Olares-compatible API endpoints that Olares One queries every 5 minutes to discover available apps.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Olares One (every 5 min)                       │
│                                                  │
│  GET  /api/v1/appstore/hash?version=X            │
│  GET  /api/v1/appstore/info                      │
│  POST /api/v1/applications/info                  │
│  GET  /api/v1/applications/{name}/chart           │
│  GET  /icons/{name}.png                          │
└──────────────────────┬──────────────────────────┘
                       │ HTTPS
                       ▼
┌─────────────────────────────────────────────────┐
│  Cloudflare Pages                               │
│  https://aimighty-market.pages.dev              │
│                                                  │
│  functions/                                     │
│    _apps.ts          ← App definitions           │
│    _lib.ts           ← MD5, chart base64,        │
│                        summary/detail builders   │
│    api/v1/appstore/info.ts     ← catalog summary │
│    api/v1/applications/info.ts ← detail (GET+POST)│
│    api/v1/applications/[app]/  │
│      chart.ts              ← chart download      │
│    _routes.json            ← routing             │
│    index.ts                ← root handler        │
└─────────────────────────────────────────────────┘
```

## Key Concepts

### App Naming Convention

App names follow the pattern: **`{prefix}{model}{runtime}`**

Examples:
- `aimembqwen3vino` — AIM + Emb(edding) + Qwen3 + OpenVINO
- `aimrerqwen3sglang` — AIM + Rer(anker) + Qwen3 + SGLang

**Rules:**
- Lowercase, no spaces, no hyphens
- Must be unique across the market
- Used as Kubernetes resource name in Olares namespace
- Used as Helm chart folder name

### App ID (MD5 Hash)

Each app gets an 8-character hex ID derived from its name:

```
appID = MD5(appName).substring(0, 8)
```

Examples:
- `aimembqwen3vino` → `84b901fe`
- `aimrerqwen3sglang` → `c9f95784`

The ID is used as the **key** in `summaries`, `details`, and `topic_lists.content`.

### Catalog Hash

The catalog hash determines whether Olares needs to re-fetch data:

```
hash = MD5(sorted list of "ID:name:version" lines joined by newline)
```

**Critical:** Olares only re-syncs when this hash changes. The hash changes when:
- An app is added or removed
- An app's `name` changes
- An app's `version` changes

**It does NOT change** when only `title`, `description`, or `fullDescription` change. To force a re-sync after metadata-only changes, **bump the version** of at least one app.

### Olares Market Backend Sync Flow

When Olares syncs a market source, it executes these steps in order:

```
Step 1: Hash Comparison  →  Compares remote hash (our API) with local cached hash
                            If match → skip, use existing data
                            If differ → proceed to Step 2

Step 2: Data Fetch        →  Fetches GET /api/v1/appstore/info from our API
                            Extracts app IDs from response
                            Stores as "pending" data

Step 3: Detail Fetch      →  POSTs to our /api/v1/applications/info with all app IDs
                            Stores raw detail data including chartName

Step 4: TaskForApiStep    →  For each pending app, POSTs chart to chartrepo service:
                            POST http://chart-repo-service:82/chart-repo/api/v2/dcr/sync-app
                            Chartrepo validates, renders, and stores the chart
                            If render fails or timeout → app moved to "render failed list"
                            ⚠ Apps in render failed list are NOT retried automatically

Step 5: Hydration         →  Periodically checks if all apps have RawPackage (chart data)
                            If RawPackage is empty → hydration incomplete
```

**Critical Observations:**
- The hash comparison uses the hash from our API response `hash` field
- If the hash matches between sync cycles, Steps 2-5 are SKIPPED entirely
- The chartrepo service (`http://chart-repo-service:82/`) stores actual chart files
- The app-service (`app-service-0`) handles installation using charts from chartrepo
- Each sync cycle runs every ~5 minutes across all configured market sources
- If Step 4 fails (timeout or render error), the app moves to "render failed list" and is not retried on subsequent cycles (because hash still matches)
- **Workaround for failed render:** Bump the version of the failed app to change the hash, forcing a full re-fetch

### Common Olares Deployment Failures

| Failure | Where it Happens | Symptom | Root Cause |
|---------|------------------|---------|------------|
| Hash match → no re-fetch | `market-deployment` sync Step 1 | Old version shown in Store | Hash unchanged; bump version |
| Chart render failure | `chartrepo` sync-app | "Render failed list" | Bad YAML in chart templates/values |
| Chartrepo timeout (3s) | `market-deployment` → `chartrepo` | "context deadline exceeded" | chartrepo busy; retry with version bump |
| Download failed | `app-service` install | "downloadFailed" state | Bad YAML in rendered templates (e.g., ConfigMap data) |
| Pod CrashLoopBackOff | Kubernetes during install | Container restarts | vLLM config error, missing GPU, bad args |

---

## Olares API Endpoints

Olares calls these endpoints in order:

### 1. `GET /api/v1/appstore/hash?version=X`

Returns whether the catalog has changed. Olares compares the returned hash with its cached hash.

**Response:**

```json
{
  "hash": "25c541272dccaac515749096f77a4543",
  "last_updated": "2026-05-09T08:15:54.139Z",
  "version": "1.0.0"
}
```

### 2. `GET /api/v1/appstore/info`

Returns the full catalog with app summaries. Called only when hash changed.

**Response structure:**

```json
{
  "version": "1.0.0",
  "hash": "...",
  "last_updated": "...",
  "data": {
    "apps": {
      "84b901fe": {
        "id": "84b901fe",
        "name": "aimembqwen3vino",
        "title": "AIM Qwen3 Emb 4B OpenVINO",
        "version": "1.0.1",
        "category": "AI",
        "description": "...",
        "fullDescription": "...",
        "icon": "https://...",
        ...
      }
    },
    "topic_lists": {
      "Newest": {
        "content": "84b901fe,c9f95784",
        ...
      }
    },
    "latest": ["aimembqwen3vino", "aimrerqwen3sglang"]
  }
}
```

**Fields Olares displays in the Store app list grid:**
- `title` — display title (if missing, falls back to `name`)
- `description` — short subtitle under the app icon
- `icon` — app icon URL
- `fullDescription` — shown in detail view

### 3. `POST /api/v1/applications/info`

Returns full details for requested apps. Olares batches ~10 app IDs at a time.

**Request body:**

```json
{
  "app_ids": ["84b901fe", "c9f95784"],
  "version": "1.0.0"
}
```

**Response:**

```json
{
  "apps": {
    "84b901fe": { /* full detail object */ }
  },
  "version": "1.0.0",
  "not_found": []
}
```

**Critical detail fields:**
- `title` — app title in Store detail page
- `i18n["en-US"].metadata.title` — i18n title (required for Store display)
- `i18n["en-US"].spec.fullDescription` — i18n full description
- `fullDescription` — full description text
- `chartName` — e.g. `"aimembqwen3vino-1.0.1.tgz"`
- `chartName` must match the key in the `CHARTS` dictionary in `_lib.ts`

### 4. `GET /api/v1/applications/{appName}/chart?fileName={chartName}`

Returns the Helm chart as a base64-decoded gzip tarball.

**Content-Type:** `application/gzip`

The chart must contain:
- `Chart.yaml` — with `name` matching app name
- `values.yaml`
- `templates/deployment.yaml` — resource names must match app name
- `templates/service.yaml` — resource names must match app name
- `OlaresManifest.yaml` — with `metadata.name` matching app name

### Helm Chart YAML Validation — Critical

**The app-service parses ALL templates as raw YAML before Helm rendering.** This means every template file must be valid YAML even before Go template variables are substituted. Common pitfalls:

| Pitfall | Example | Fix |
|---------|---------|-----|
| **Duplicate keys in `values.yaml`** | Two `olaresEnv:` sections at different lines | Merge into one section |
| **Block scalar indentation** | HTML in `index.html: \|` with varying indentation (e.g., a `<pre>` block with 6-space child lines + 2-space continuation lines) | **All lines in a `\|` block must have ≥ the initial indentation** (usually 4 spaces for data under a ConfigMap) |
| **CSS `{` in block scalars** | `.endpoint{` in a `\|` block | A `\|` block scalar preserves all content; this is safe as long as indentation is consistent |
| **Template expressions in strings** | `{{ .Values.xxx }}` in YAML that's not inside a `\|` block | Move into a `\|` block or quote properly |

**Testing locally:**

```bash
# Validate YAML rendering (Go templates substituted)
helm template charts/<appname>/ --dry-run=client

# Check for YAML parse errors
helm package charts/<appname>/ --dry-run 2>&1
```

**Note:** `helm template` substitutes Go templates before YAML parsing, so it can mask issues where template syntax changes YAML structure. The app-service parses rendered output, so any line that is syntactically valid YAML after rendering should work.

---

## The Golden Rule: Version Consistency

**This is the #1 source of deployment failures.** The version number must be identical in ALL of these locations:

| Location | File | Field |
|----------|------|-------|
| Market source app definition | `functions/_apps.ts` | `metadata.version` |
| Chart dictionary key | `functions/_lib.ts` | `"<name>-<version>.tgz"` |
| Helm Chart manifest | app repo `Chart.yaml` | `version` |
| Olares manifest | app repo `OlaresManifest.yaml` | `metadata.version` + `spec.versionName` |

**What happens when they don't match:**
- `getChartByAppName()` builds the key as `"${name}-${version}.tgz"` from `_apps.ts`
- It looks up this key in the `CHARTS` dictionary in `_lib.ts`
- If the key doesn't exist → 404 → Olares cannot download the chart → falls back to old cached data (showing the old version)
- **From the user's perspective it looks like nothing changed**

**Always update all four locations together.**

---

## How to Add a New App

### Step 1: Create the App Repository

Create a new GitHub repo for the app (e.g., `bayerhazard/aimighty-newapp`).

The repo must contain **two** OlaresManifest.yaml files — one at the repo root (for the Store metadata, env vars, descriptions) and one inside the Helm chart folder (for the installation). **Both must have identical version numbers and upgradeDescription.**

```
repo-root/
  icon.png                    ← app icon (512x512 recommended)
  OlaresManifest.yaml         ← ROOT manifest (full metadata, envs, descriptions)
  <appname>/                  ← Helm chart folder (name must match app name)
    Chart.yaml
    OlaresManifest.yaml       ← CHART manifest (must match root manifest versions/changelog!)
    values.yaml
    templates/
      deployment.yaml
      service.yaml
```

**Chart.yaml** must have:

```yaml
apiVersion: v2
name: <appname>              ← must match app name exactly
version: 1.0.0
```

**Entrances** — critical for app state and dashboard:

```yaml
entrances:
- name: <appname>            ← must match the app name (NOT a generic name like "reranker")
  port: 8080
  title: "Service Title"
  host: <appname>            ← must match the app name (this is the K8s service name)
  authLevel: internal
  invisible: false
  openMethod: window         ← REQUIRED if the app has a web dashboard/UI
```

**Without `openMethod: window`:** Olares shows the app as "running" and clicking does nothing.
**With `openMethod: window`:** Olares shows "open" and clicking opens the dashboard in a browser tab.

**Env var types** — must match the actual value type:

```yaml
- envName: TZ
  type: string               ← "Etc/UTC" is a string, NOT int
  default: "Etc/UTC"
```

### Step 2: Package the Helm Chart

```bash
helm package <appname>/
# Creates: <appname>-1.0.0.tgz
```

### Step 3: Base64-Encode the Chart

```bash
base64 -i <appname>-1.0.0.tgz | tr -d '\n'
```

### Step 4: Update `functions/_apps.ts`

Add a new entry to the `apps` array:

```typescript
{
  metadata: {
    name: "<appname>",
    version: "1.0.0",
    icon: "https://github.com/bayerhazard/<repo>/raw/main/icon.png",
    title: { en: "Human Readable Title" },
    description: { en: "Short description" },
    fullDescription: "Long description...",
    upgradeDescription: "v1.0.0: Initial release.",
    categories: ["AI", "Developer Tools"],
    developer: "Aimighty",
    supportArch: ["amd64"],
    requiredCpu: "2",
    requiredMemory: "24Gi",
    requiredDisk: "50Gi",
    requiredGpu: "0",
  },
  spec: {
    type: "app",
    entrance: [
      { name: "<service-name>", title: { en: "Service Title" }, port: 8080 },
    ],
    permission: [],
    middleware: [],
    options: { resources: { cpu: "2", memory: "24Gi", disk: "50Gi" } },
  },
}
```

### Step 5: Update `functions/_lib.ts`

Add the base64-encoded chart to the `CHARTS` dictionary:

```typescript
const CHARTS: Record<string, string> = {
  // existing charts...
  "<appname>-1.0.0.tgz": "<base64-string>",
};
```

### Step 6: Commit, Push, and Deploy

```bash
cd /Users/marc/Documents/OpenCode/aimighty
git add functions/ && git commit -m "add <appname> v1.0.0" && git push
export PATH="/usr/local/bin:$PATH"
./node_modules/.bin/wrangler pages deploy functions/ --project-name=aimighty-market
```

**Important:** Always commit before deploying. The GitHub auto-deploy will otherwise deploy stale code, and manual deploy + git push out of sync causes version mismatches.

### Step 7: Verify

```bash
# Check summary endpoint
curl -s "https://aimighty-market.pages.dev/api/v1/appstore/info" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for k,v in d['data']['apps'].items():
    print(f'{k}: v={v[\"version\"]} title={v.get(\"title\",\"MISSING\")}')"

# Check chart download
curl -s -o /dev/null -w "chart: %{http_code}\n" \
  "https://aimighty-market.pages.dev/api/v1/applications/<appname>/chart"
```

---

## How to Update an Existing App

### Updating Metadata Only (title, description, etc.)

1. Update the entry in `functions/_apps.ts`
2. **Bump the `version`** of the app (e.g., `1.0.0` → `1.0.1`) — this is mandatory
3. **Generate a fresh base64 string** — do NOT reuse the old base64 even if the chart didn't change. Extract the existing chart, re-compress, and re-encode:
   ```bash
   # Extract old chart from _lib.ts (example using Python)
   python3 -c "
   import re, base64, gzip, io
   with open('functions/_lib.ts') as f: c = f.read()
   m = re.search(r'\"<name>-<old-version>.tgz\":\s*\"([^\"]+)\"', c)
   raw = base64.b64decode(m.group(1))
   data = gzip.decompress(raw)
   buf = io.BytesIO()
   with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=9, mtime=0) as gz: gz.write(data)
   print(base64.b64encode(buf.getvalue()).decode())
   " | pbcopy
   ```
   **Warum:** Der alte Base64-String kann deploy-seitig korrupt werden (Cloudflare error 1101). Einmaliges Dekodieren und Neu-Kodieren mit cleanem gzip-Header behebt das.
4. **Replace the key and value** in `functions/_lib.ts` — neuer Key `"<name>-1.0.1.tgz"` mit frischem Base64
5. Commit, push, deploy

### Updating the Chart (new Helm chart)

1. Update files in the app repository (`Chart.yaml`, `OlaresManifest.yaml`, templates, etc.)
2. Update `OlaresManifest.yaml` and `Chart.yaml` with new version
3. Package: `helm package <appname>/`
4. Base64-encode the new chart: `base64 -i <appname>-1.0.1.tgz | tr -d '\n'`
5. Update `_apps.ts`: bump `version`, update metadata
6. Update `_lib.ts`: replace the chart entry with new key `"<appname>-1.0.1.tgz"` and new base64 string
7. **Also update the app repo** (`Chart.yaml`, `OlaresManifest.yaml`) and commit + push
8. Commit, push, deploy the market source

**Verification checklist after update:**

```bash
# 1. Summary shows new version + title
curl -s "https://aimighty-market.pages.dev/api/v1/appstore/info" | python3 -m json.tool

# 2. Each app's chart downloads successfully (200, NOT 500)
for app in aimembqwen3vino aimrerqwen3sglang; do
  code=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://aimighty-market.pages.dev/api/v1/applications/${app}/chart")
  echo "${app}: ${code}"
done
```

---

## vLLM Configuration — Critical

**This is the #1 cause of pod crashes at install time.** The vLLM container command and arguments must be compatible with the vLLM version in use.

### The `--task score` Problem

```
Command:  python3 -m vllm.entrypoints.openai.api_server
Args:     --model ... --task score  ← CRASHES on vLLM v0.13+
```

**vLLM v0.11+** moved the `--task` argument from `api_server.py` CLI to the `vllm serve` command. If you use `python3 -m vllm.entrypoints.openai.api_server`, do NOT include `--task score`. The `/v1/score` and `/classify` endpoints are auto-enabled when vLLM detects a sequence classification model.

**Solutions:**

| Approach | Command | Pros | Cons |
|----------|---------|------|------|
| Remove `--task` | `python3 -m vllm.entrypoints.openai.api_server` without `--task` | Works with all vLLM versions | `/classify` endpoint relies on auto-detect |
| Proxy wrapper | Sidecar container that translates `/v1/rerank` → `/classify` | Works without native rerank support | Extra container, latency overhead |
| Use `vllm serve` | `vllm serve <model> --task score --port 30000` | Full CLI support | Different image may be needed |

**The proxy approach used for aimrerqwen3vllm:** A Python aiohttp sidecar translates Cohere/Jina-style `/v1/rerank` requests to vLLM's `/classify` API. The `deployment.yaml` has a `rerank-proxy` container that receives `/v1/rerank` via nginx routing and forwards to `localhost:30000/classify`.

### vLLM Image Tag Policy

| Tag | Reliability | Best for |
|-----|-------------|----------|
| `latest` | ❌ May break on upgrade | Development only |
| `v0.10.0` (pinned) | ✅ Known working | Production stability |
| `v0.13.0` | ⚠️ Needs --task fix | Latest features, requires workarounds |

**Rule:** When adding `--task score`, pin the image to a known working version. When using `latest`, never add `--task score`.

---

## Olares Cache Behavior — Critical

Olares caches app data aggressively. When changes don't appear in the Store:

1. **First:** Verify the API returns correct data (see verification commands above)
2. **If API is correct but Store is wrong:** In Olares UI, **completely remove** the Market Source, then **re-add** it with `https://aimighty-market.pages.dev`
3. **Do NOT just click "synchronize"** — Olares' sync button does not clear its internal cache
4. Wait up to 5 minutes for Olares to auto-sync after re-adding

**Why this happens:** Olares stores app details in its local database keyed by the catalog hash. When the hash changes, it should fetch new data — but in practice, Olares often retains old cached entries. Removing and re-adding the Market Source forces a full cache invalidation.

---

## File Structure of the Market Source

```
aimighty/                          ← /Users/marc/Documents/OpenCode/aimighty
  .gitignore
  package.json
  wrangler.toml                   ← name: "aimighty-market"
  functions/
    _apps.ts                      ← APP DEFINITIONS (edit here to add/update apps)
    _lib.ts                       ← CHARTS dict + helper functions
    _routes.json                  ← routing config
    index.ts                      ← root handler
    api/v1/
      appstore/
        info.ts                   ← GET: catalog summary
      applications/
        info.ts                   ← GET + POST: app details
        [app]/
          chart.ts                ← GET: chart download
```

---

## Critical Rules

1. **`name` must be consistent everywhere:** `_apps.ts` → `Chart.yaml` → `OlaresManifest.yaml` → Helm templates → Kubernetes resources
2. **Version must be consistent everywhere:** `_apps.ts` → `CHARTS` key → `Chart.yaml` → `OlaresManifest.yaml`
3. **`i18n.en-US.metadata.title` is required** for Store to show human-readable titles
4. **`i18n.en-US.spec.fullDescription` is required** for Store detail page
5. **Chart key in `CHARTS`** must be `"<name>-<version>.tgz"` and match `chartName` in detail response
6. **`latest` field** must contain app **names** (not MD5 hashes)
7. **`topic_lists.content`** must contain MD5 **hashes** (comma-separated)
8. **`summaries` and `details` keys** must be MD5 **hashes**
9. **Always bump version** when changing metadata-only to trigger Olares re-sync
10. **`node_modules/` and `.wrangler/` must NEVER be committed** (`.gitignore` handles this)
11. **Only `functions/` is deployed** — other files are not sent to Cloudflare
12. **Always commit before deploying** — manual `wrangler deploy` deploys local files, but GitHub auto-deploy uses the pushed state. Keeping them in sync prevents version mismatches.
13. **Nie alten Base64-String wiederverwenden** — auch wenn das Chart sich nicht ändert, `base64 -i` jedes Mal neu ausführen. Der deploy-seitig optimierte Base64 kann durch Cloudflare's Kompilierung korrumpiert werden (error 1101).
14. **`values.yaml` darf keine doppelten Keys haben** — besonders `olaresEnv` nur einmal definieren, sonst YAML-Parse-Fehler bei chartrepo sync
15. **Alle Zeilen in einem `|` Block-Skalar muessen ≥ den Einzug der ersten Zeile haben** — sonst bricht YAML den Skalar ab und parst den Rest als Keys. Besonders gefaehrlich bei HTML/CSS/JS in ConfigMaps
16. **vLLM `latest` nie mit `--task score` verwenden** — nur `vllm serve` CLI unterstuetzt `--task`, nicht `api_server.py`

---

## Diagnosing Olares Sync / Install Failures

When an app fails to install or doesn't appear in the Store, follow this systematic approach:

### 1. Verify Market Source API

```bash
# Check hash and versions
curl -s "https://aimighty-market.pages.dev/api/v1/appstore/info" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for k,v in d['data']['apps'].items():
    print(f'{k}: {v[\"name\"]} v={v[\"version\"]}')
print(f'hash={d[\"hash\"]}')"

# Check chart download
curl -s -o /dev/null -w "chart: %{http_code}\n" \
  "https://aimighty-market.pages.dev/api/v1/applications/<appname>/chart"
```

### 2. Check Olares Market Backend Logs

```bash
# Check sync cycles for our source
ssh olares@172.20.0.4 "kubectl logs -n os-framework market-deployment-<suffix> 2>/dev/null | grep 'market.AImighty'"

# Check if hash was detected as changed
ssh olares@172.20.0.4 "kubectl logs -n os-framework market-deployment-<suffix> 2>/dev/null | grep 'hash_comparison_step.*AImighty'"

# Check raw data processing (app IDs in pending)
ssh olares@172.20.0.4 "kubectl logs -n os-framework market-deployment-<suffix> 2>/dev/null | grep '84b901fe\|c1b073d1'"

# Check chart repo sync-app errors
ssh olares@172.20.0.4 "kubectl logs -n os-framework market-deployment-<suffix> 2>/dev/null | grep 'TaskForApiStep\|render failed'"
```

**Key app IDs:**
- Embedder: `84b901fe` (`aimembqwen3vino`)
- Reranker: `c1b073d1` (`aimrerqwen3vllm`)

### 3. Check Chartrepo Service

```bash
ssh olares@172.20.0.4 "kubectl logs -n os-framework chartrepo-deployment-<suffix> --tail=50"
```

Look for `sync-app` requests from our market source. If timeout occurs, the market backend's 3s deadline was exceeded.

### 4. Check App-Service (Install Phase)

```bash
# Check download errors
ssh olares@172.20.0.4 "kubectl logs -n os-framework app-service-0 2>/dev/null | grep -i 'downloadFailed\|YAML parse error'"

# Check install progress
ssh olares@172.20.0.4 "kubectl logs -n os-framework app-service-0 2>/dev/null | grep 'aimrerqwen3vllm'"
```

### 5. Check Pod Status (Runtime Phase)

```bash
ssh olares@172.20.0.4 "kubectl get pods -n aimrerqwen3vllm-aimighty"

# Check crash loop logs
ssh olares@172.20.0.4 "POD=\$(kubectl get pods -n aimrerqwen3vllm-aimighty -o jsonpath='{.items[0].metadata.name}') && \
  kubectl logs -n aimrerqwen3vllm-aimighty \$POD -c aimrerqwen3vllm --tail=50"

# Check container exit codes
ssh olares@172.20.0.4 "kubectl get pods -n aimrerqwen3vllm-aimighty -o yaml | grep 'exitCode\|reason'"
```

---

## Deployment Commands

```bash
# Navigate to market source repo
cd /Users/marc/Documents/OpenCode/aimighty

# Always commit changes first
git add functions/ && git commit -m "describe change" && git push

# Manual deploy (recommended for immediate effect)
export PATH="/usr/local/bin:$PATH"
./node_modules/.bin/wrangler pages deploy functions/ --project-name=aimighty-market

# Verify after deploy
curl -s "https://aimighty-market.pages.dev/api/v1/appstore/info" | python3 -m json.tool
curl -s -o /dev/null -w "chart: %{http_code}\n" \
  "https://aimighty-market.pages.dev/api/v1/applications/<appname>/chart"
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Title shows as app name (e.g. `aimembqwen3vino`) | `i18n` or `title` field missing/empty | Add `i18n.en-US.metadata.title` in `buildDetail()` |
| Full description empty | `fullDescription` missing in summary/detail | Add to `buildSummary()` and `buildDetail()` |
| Olares not picking up changes | Catalog hash unchanged | Bump version of any app to change hash |
| Olares not picking up changes (after version bump) | Olares has cached old data | **Remove + re-add** Market Source in Olares UI (sync alone is not enough) |
| Version shows old value in Store but API shows new | Chart download fails (404) | `CHARTS` key doesn't match `_apps.ts` version — rename key to match |
| Chart 404 after version bump | `getChartByAppName()` builds `"name-version.tgz"` and doesn't find it | Update `CHARTS` dictionary key to new version |
| 404 on `/applications/info` | GET handler missing | Add `onRequestGet()` handler |
| Push rejected (large files) | `node_modules` in git | Run `git rm -r --cached node_modules/` and amend |
| Deploy fails (wrangler not found) | Node.js not in PATH | `export PATH="/usr/local/bin:$PATH"` |
| Olares shows 1.0.0 but API says 1.0.1 | Olares cannot download chart → falls back to cache | Check chart endpoint returns 200, then remove + re-add Market Source |
| Chart download returns HTTP 500 (error 1101) | Base64-String in `_lib.ts` deploy-seitig korrupt | Chart extrahieren, neu komprimieren und frisch base64-en (siehe "Updating Metadata Only" Schritt 3) |
| Chart 500 bleibt nach Base64-Neugenerierung | Cloudflare Pages Skript-Limit überschritten | Chart-Datei extern hosten (GitHub Raw) statt Base64-Inlining |
| **Cloudflare cached alte Chart-Datei trotz neuem Deploy** | Cloudflare kompiliert TS → JS und cached die Ausgabe. `--skip-caching` hilft oft nicht | **Wrangler cache loeschen:** `rm -rf .wrangler/cache/*` + `rm -rf .wrangler/state/v3/pages` + redeploy. Falls immer noch gecached: **warten** (erholt sich innerhalb weniger Stunden) |
| **Website `aimighty.de` zeigt Market Source API** | GitHub Auto-Deploy auf `aimighty` Projekt hat Website durch Market Source ersetzt | Website manuell deployen: `wrangler pages deploy . --project-name=aimighty` + **GitHub Auto-Deploy im Cloudflare Dashboard deaktivieren** |
| **App zeigt "running" statt "open"** | `openMethod: window` fehlt in `entrances` der OlaresManifest.yaml | `openMethod: window` zum Entrance hinzufuegen, Version bumpen, neu deployen |
| **"Unable to install app, Incompatible with your Olares"** | `entrances[0].name` und `host` stimmen nicht mit `metadata.name` ueberein | Beides auf den App-Namen setzen (z.B. `aimrerqwen3vllm`) |
| **Reranker Chart wird nicht geladen (RawPackage empty)** | Chart-Datei im `_lib.ts` fehlt oder hat falschen Key | Chart packen, base64-encodieren, in `_lib.ts` CHARTS-Map einfuegen |
| **"context deadline exceeded" bei sync-app** | chartrepo service antwortet nicht innerhalb von 3s | Chartrepo ist ausgelastet; Version bumpen und neu deployen (transienter Fehler) |
| **"YAML parse error on ... ConfigMap" bei "Download failed"** | Block-Skalar in `configmap.yaml` hat inkonsistenten Einzug | Alle Zeilen in `\|`-Block muessen ≥ urspruenglichen Einzug haben (meist 4 Spaces) |
| **"unrecognized arguments: --task" → Container CrashLoopBackOff** | vLLM `api_server.py` unterstuetzt `--task` nicht (nur `vllm serve` CLI) | `--task score` aus den args entfernen; Proxy nutzt `/classify` stattdessen |
| **App in "render failed list" nach Hash-Change** | chartrepo render/timeout Fehler bei Hydration-Step | Hash des betroffenen Apps aendern (Version bumpen), um kompletten Re-Fetch zu erzwingen |
| **K8s Service-Name stimmt nicht mit Entrance-Host ueberein** | Helm templates verwenden anderen Namen als OlaresManifest `entrances[0].host` | Service.metadata.name und Deployment.metadata.name muessen mit entrance host uebereinstimmen |

---

## Olares One Hardware Context

- CPU: Intel Core Ultra 9 275HX (Arrow Lake-S)
- RAM: 96 GB
- GPU: NVIDIA RTX 5090 (Blackwell)
- Apps should be optimized for this hardware profile
