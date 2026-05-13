#!/usr/bin/env bash
# Codifies the lessons from Phase 4 (v0.1.7 → v0.1.17). Runs in CI before
# images are built, and is safe + fast to run locally. Each check has a
# comment pointing at the docs/HANDOFF.md section that explains why it
# matters.
#
# Exit codes:
#   0  — all checks passed
#   1  — at least one check failed (see stderr for which)

set -euo pipefail

# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CHART_FILE="olares/Chart.yaml"
MANIFEST_FILE="olares/OlaresManifest.yaml"
VALUES_FILE="olares/values.yaml"
TEMPLATES_DIR="olares/templates"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

FAILED=0
fail() {
  red "  ✗ $*"
  FAILED=$((FAILED + 1))
}
ok() {
  green "  ✓ $*"
}
section() {
  printf "\n%s\n" "── $* ──"
}

extract() {
  # extract <file> <yaml-path-like-prefix>
  # Tiny grep-based reader. Avoids needing yq.
  grep -E "^[[:space:]]*${2}:" "$1" | head -1 | sed -E "s/.*${2}:[[:space:]]*['\"]?([^'\"#]+)['\"]?.*/\1/" | xargs
}

# ---------------------------------------------------------------------------
# 1. Version sync (Marc's Golden Rule — HANDOFF §7e)
# ---------------------------------------------------------------------------

section "version sync (Chart.yaml ↔ OlaresManifest)"

CHART_VERSION="$(extract "$CHART_FILE" "version")"
CHART_APP_VERSION="$(extract "$CHART_FILE" "appVersion")"
MANIFEST_VERSION="$(extract "$MANIFEST_FILE" "  version")"
MANIFEST_VERSIONNAME="$(grep -E "^[[:space:]]*versionName:" "$MANIFEST_FILE" | head -1 | sed -E "s/.*versionName:[[:space:]]*['\"]?([^'\"#]+)['\"]?.*/\1/" | xargs)"

if [[ "$CHART_VERSION" == "$CHART_APP_VERSION" ]]; then
  ok "Chart.yaml: version == appVersion ($CHART_VERSION)"
else
  fail "Chart.yaml: version ($CHART_VERSION) != appVersion ($CHART_APP_VERSION)"
fi

if [[ "$CHART_VERSION" == "$MANIFEST_VERSION" ]]; then
  ok "Chart.yaml.version == OlaresManifest.metadata.version ($CHART_VERSION)"
else
  fail "Chart.yaml.version ($CHART_VERSION) != OlaresManifest.metadata.version ($MANIFEST_VERSION)"
fi

if [[ "$CHART_APP_VERSION" == "$MANIFEST_VERSIONNAME" ]]; then
  ok "Chart.yaml.appVersion == OlaresManifest.spec.versionName ($CHART_APP_VERSION)"
else
  fail "Chart.yaml.appVersion ($CHART_APP_VERSION) != OlaresManifest.spec.versionName ($MANIFEST_VERSIONNAME)"
fi

# ---------------------------------------------------------------------------
# 2. NEVER use .Files.Get — Olares chart renderer doesn't support it
#    (HANDOFF §7g.2)
# ---------------------------------------------------------------------------

section "no .Files.Get in templates"

# Only fail on real template usage: must be inside Helm template delimiters
# `{{ ... }}`. Comments mentioning .Files by name (in `#` or YAML strings) are fine.
if grep -rEn "\{\{[^}]*\.Files\.(Get|Glob|AsConfig|AsSecrets)" "$TEMPLATES_DIR" >/dev/null 2>&1; then
  fail ".Files.* used inside {{ }} — Olares' chart renderer will reject upload"
  grep -rEn "\{\{[^}]*\.Files\.(Get|Glob|AsConfig|AsSecrets)" "$TEMPLATES_DIR" | sed 's/^/    /'
else
  ok "no .Files.* template invocations"
fi

# ---------------------------------------------------------------------------
# 3. NEVER use Helm hooks that need DB/middleware access
#    (HANDOFF §7g.1 — chicken-and-egg: ns-owner label is set after install)
# ---------------------------------------------------------------------------

section "no Helm hooks (chicken-and-egg ns-owner)"

if grep -rn "helm\.sh/hook:" "$TEMPLATES_DIR" >/dev/null 2>&1; then
  fail "helm.sh/hook found in templates — DB-touching hooks can never reach DB before NS labels exist"
  grep -rn "helm\.sh/hook" "$TEMPLATES_DIR" | sed 's/^/    /'
else
  ok "no helm.sh/hook annotations"
fi

# ---------------------------------------------------------------------------
# 4. NEVER use runAsInternal: true — Studio-only Olares feature
#    (HANDOFF §7g.3 — breaks frontend Envoy check-auth init-container)
# ---------------------------------------------------------------------------

section "no runAsInternal: true"

if grep -E "^[[:space:]]*runAsInternal:[[:space:]]*true" "$MANIFEST_FILE" >/dev/null 2>&1; then
  fail "runAsInternal: true in OlaresManifest — Studio-only flag, breaks Envoy"
  grep -nE "runAsInternal:" "$MANIFEST_FILE" | sed 's/^/    /'
else
  ok "no runAsInternal: true"
fi

# ---------------------------------------------------------------------------
# 5. Image-tag sanity (HANDOFF §7e — values.yaml tags should be in sync)
# ---------------------------------------------------------------------------

section "image tags in values.yaml"

TAGS=$(grep -E "^[[:space:]]+tag:" "$VALUES_FILE" | sed -E "s/.*tag:[[:space:]]*([^[:space:]#]+).*/\1/" | sort -u)
TAG_COUNT=$(echo "$TAGS" | wc -l | tr -d ' ')
if [[ "$TAG_COUNT" -eq 1 ]]; then
  ok "all image tags align ($(echo $TAGS))"
else
  yellow "  ! image tags diverge — usually a mistake, but allowed for partial rebuilds:"
  echo "$TAGS" | sed 's/^/    /'
fi

# ---------------------------------------------------------------------------
# 6. SQL drift: supabase/migrations + supabase/seed.sql == olares/files/
#    (HANDOFF §7g.2 — single source of truth)
# ---------------------------------------------------------------------------

section "SQL drift (supabase/ vs olares/files/)"

drift=0
for src in supabase/migrations/*.sql; do
  name=$(basename "$src")
  dst="olares/files/$name"
  if [[ ! -f "$dst" ]]; then
    fail "missing $dst (run: python3 scripts/regen-migrations.py)"
    drift=$((drift + 1))
    continue
  fi
  if ! diff -q "$src" "$dst" >/dev/null 2>&1; then
    fail "$dst differs from $src (run: python3 scripts/regen-migrations.py)"
    drift=$((drift + 1))
  fi
done

if [[ -f supabase/seed.sql ]]; then
  if [[ ! -f olares/files/seed.sql ]]; then
    fail "missing olares/files/seed.sql (run: python3 scripts/regen-migrations.py)"
    drift=$((drift + 1))
  elif ! diff -q supabase/seed.sql olares/files/seed.sql >/dev/null 2>&1; then
    fail "olares/files/seed.sql differs from supabase/seed.sql"
    drift=$((drift + 1))
  fi
fi

if [[ "$drift" -eq 0 ]]; then
  ok "supabase/ and olares/files/ in sync"
fi

# ---------------------------------------------------------------------------
# 7. ConfigMap regen check: re-run the generator and require empty diff
#    (HANDOFF §7g.2 — inlined SQL must match olares/files/)
# ---------------------------------------------------------------------------

section "configmap-migrations.yaml is regenerable"

if command -v python3 >/dev/null 2>&1; then
  # Backup current template so we can restore if the working tree is dirty.
  cp olares/templates/configmap-migrations.yaml /tmp/configmap-migrations.backup
  python3 scripts/regen-migrations.py >/dev/null
  if diff -q /tmp/configmap-migrations.backup olares/templates/configmap-migrations.yaml >/dev/null 2>&1; then
    ok "configmap-migrations.yaml matches generator output"
    rm /tmp/configmap-migrations.backup
  else
    fail "configmap-migrations.yaml is out of date — commit the regenerated version"
    cp /tmp/configmap-migrations.backup olares/templates/configmap-migrations.yaml
    rm /tmp/configmap-migrations.backup
  fi
else
  yellow "  ! python3 not available — skipping regen check"
fi

# ---------------------------------------------------------------------------
# 8. helm lint + helm template render
# ---------------------------------------------------------------------------

section "helm lint + template"

if command -v helm >/dev/null 2>&1; then
  if helm lint olares/ -f olares/values-olares-stub.yaml >/tmp/helm-lint.log 2>&1; then
    ok "helm lint passes"
  else
    fail "helm lint failed:"
    sed 's/^/    /' /tmp/helm-lint.log
  fi
  if helm template insilo olares/ -f olares/values-olares-stub.yaml >/tmp/helm-template.log 2>&1; then
    ok "helm template renders"
  else
    fail "helm template failed:"
    sed 's/^/    /' /tmp/helm-template.log
  fi
else
  yellow "  ! helm not installed — skipping lint/template"
fi

# ---------------------------------------------------------------------------
# 9. OlaresManifest required fields
#    (HANDOFF §6 + Olares spec)
# ---------------------------------------------------------------------------

section "OlaresManifest required fields"

for field in "name:" "appid:" "title:" "version:" "icon:" "requiredDisk:" "supportArch:"; do
  if grep -E "^[[:space:]]*${field}" "$MANIFEST_FILE" >/dev/null 2>&1; then
    ok "$field present"
  else
    fail "$field missing in OlaresManifest"
  fi
done

# App name regex: ^[a-z0-9]{1,30}$
NAME="$(extract "$MANIFEST_FILE" "  name")"
if [[ "$NAME" =~ ^[a-z0-9]{1,30}$ ]]; then
  ok "metadata.name '$NAME' matches Olares regex ^[a-z0-9]{1,30}$"
else
  fail "metadata.name '$NAME' violates Olares regex ^[a-z0-9]{1,30}$"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

printf "\n"
if [[ "$FAILED" -gt 0 ]]; then
  red "✗ $FAILED check(s) failed"
  exit 1
else
  green "✓ all checks passed (version $CHART_VERSION)"
fi
