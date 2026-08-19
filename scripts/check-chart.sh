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
ROOT_MANIFEST_FILE="OlaresManifest.yaml"
VALUES_FILE="olares/values.yaml"
TEMPLATES_DIR="olares/templates"
VALUES_STUB="olares/values-olares-stub.yaml"

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
skip() {
  yellow "  – $*"
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
# 1b. Root manifest ↔ chart manifest sync
#     Olares Market requires TWO OlaresManifest.yaml files (Store metadata +
#     installation), with identical version + versionName. See
#     docs/MARKET_SOURCE_PLAYBOOK.md:297. Missed for v0.1.18–v0.1.60 because
#     release.sh only bumped the chart-internal copy; fixed since v0.1.61.
# ---------------------------------------------------------------------------

section "root manifest ↔ chart manifest sync"

if [[ ! -f "$ROOT_MANIFEST_FILE" ]]; then
  fail "$ROOT_MANIFEST_FILE missing — Olares Market expects a root-level manifest"
else
  ROOT_MANIFEST_VERSION="$(extract "$ROOT_MANIFEST_FILE" "  version")"
  ROOT_MANIFEST_VERSIONNAME="$(grep -E "^[[:space:]]*versionName:" "$ROOT_MANIFEST_FILE" | head -1 | sed -E "s/.*versionName:[[:space:]]*['\"]?([^'\"#]+)['\"]?.*/\1/" | xargs)"

  if [[ "$ROOT_MANIFEST_VERSION" == "$MANIFEST_VERSION" ]]; then
    ok "root vs chart: metadata.version matches ($ROOT_MANIFEST_VERSION)"
  else
    fail "root OlaresManifest.metadata.version ($ROOT_MANIFEST_VERSION) != chart ($MANIFEST_VERSION)"
  fi

  if [[ "$ROOT_MANIFEST_VERSIONNAME" == "$MANIFEST_VERSIONNAME" ]]; then
    ok "root vs chart: spec.versionName matches ($ROOT_MANIFEST_VERSIONNAME)"
  else
    fail "root OlaresManifest.spec.versionName ($ROOT_MANIFEST_VERSIONNAME) != chart ($MANIFEST_VERSIONNAME)"
  fi
fi

# ---------------------------------------------------------------------------
# 1c. upgradeDescription must announce the version actually being shipped
#     release.sh bumps the version FIELDS but not the release-notes TEXT, so
#     the headline silently ages unless someone rewrites it. Same drift family
#     as 1b, one level down. The notes are handwritten by design — this only
#     checks that the version in the first line matches.
# ---------------------------------------------------------------------------

section "upgradeDescription announces current version"

for mf in "$MANIFEST_FILE" "$ROOT_MANIFEST_FILE"; do
  [[ -f "$mf" ]] || continue
  # First non-blank line after the `upgradeDescription: |` block opener.
  HEADLINE="$(awk '/^[[:space:]]*upgradeDescription:/{f=1;next} f&&NF{print;exit}' "$mf")"
  if [[ -z "$HEADLINE" ]]; then
    fail "$mf: upgradeDescription is empty"
  elif [[ "$HEADLINE" == *"$CHART_VERSION"* ]]; then
    ok "$mf: headline mentions $CHART_VERSION"
  else
    fail "$mf: upgradeDescription headline does not mention $CHART_VERSION — stale release notes?"
    echo "      $HEADLINE" | sed 's/^/    /'
  fi
done

# ---------------------------------------------------------------------------
# 1d. Olares system dependency must be a CLOSED version range
#     An open '>=x.y.z' is rejected by the Market upload with HTTP 400:
#     "must restrict the Olares system version to >=A,<B". Cost us the
#     v0.1.61 upload. The exact bounds come from the Market's error message
#     for the current apiVersion — this check only enforces that an upper
#     bound exists at all.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 1d0. Der offizielle Validator, wenn er da ist.
#      `olares-cli chart lint` fährt nach eigener Aussage dieselbe Pipeline,
#      mit der der Store ein Chart einliest — er kennt die Regeln also
#      besser als alles, was wir hier nachbauen. Fehlt der Befehl (CI,
#      frische Maschine), wird übersprungen statt zu scheitern; die
#      handgeschriebenen Guards unten decken den Rest ab.
# ---------------------------------------------------------------------------

section "olares-cli chart lint (offizieller Validator)"

if command -v olares-cli >/dev/null 2>&1; then
  # Das gepackte Chart prüfen, nicht den Ordner: der Validator verlangt
  # Ordnername == Chart-Name, und unser Ordner heißt "olares/", nicht
  # "insilo/". Im Tarball heißt die Wurzel korrekt "insilo/".
  LINT_TMP="$(mktemp -d)"
  trap 'rm -rf "$LINT_TMP"' EXIT
  # Packen und Prüfen getrennt melden. Zusammengefasst verschluckte ein
  # Packfehler seine eigene Meldung und lief unter `set -u` in eine
  # ungesetzte Variable — die Ursache stand dann nirgends.
  if ! PACK_OUT="$(olares-cli chart package olares/ -o "$LINT_TMP" 2>&1)"; then
    fail "olares-cli chart package: ${PACK_OUT}"
  elif ! LINT_OUT="$(olares-cli chart lint "$LINT_TMP"/*.tgz --with-rbac --with-security-context 2>&1)"; then
    fail "olares-cli chart lint: ${LINT_OUT}"
  else
    ok "olares-cli chart lint: OK"
  fi
else
  skip "olares-cli nicht im PATH — offizieller Validator übersprungen"
fi

# ---------------------------------------------------------------------------
# 1d1. Neue Wertschlüssel dürfen nicht direkt dereferenziert werden.
#
#      Ein Upgrade — ob per `helm --reuse-values` oder über den Markt —
#      spielt die beim Installieren gespeicherten Werte zurück und mischt
#      die Vorgaben des neuen Charts NICHT ein. Ein Schlüssel, den es in
#      der Vorversion noch nicht gab, fehlt dann zur Laufzeit. Steht im
#      Template `.Values.neu.feld`, stirbt das Rendern mit "nil pointer"
#      und das Upgrade scheitert, bevor irgendetwas passiert.
#
#      Gesehen bei v0.1.77: der neue `stt:`-Block ließ jedes Markt-Upgrade
#      auflaufen, obwohl jede andere Prüfung grün war.
#
#      Nachstellen lässt sich das nicht durch Rendern: `helm template -f`
#      MISCHT die übergebene Datei mit den Chart-Vorgaben, der Schlüssel
#      ist also immer da. Deshalb statisch: welche Top-Level-Schlüssel sind
#      neu gegenüber dem letzten Tag, und greift ein Template direkt
#      darauf zu?
#
#      Sichere Schreibweise: (default (dict) .Values.neu).feld | default ""
# ---------------------------------------------------------------------------

section "neue Wertschlüssel sind upgrade-sicher dereferenziert"

# Höchster Tag, der NICHT die gerade gebaute Version ist — nach einem
# Release liefert `git describe` sonst den soeben gesetzten.
# Jede Pipeline hier braucht `|| true`. Unter `set -euo pipefail` beendet
# ein grep ohne Treffer das ganze Skript — und "kein Treffer" ist hier ein
# normaler Fall: eine frische Prüfung ohne Tags, oder ein Repo, in dem der
# einzige Tag die gerade gebaute Version ist. Genau daran ist der Release
# v0.1.79 gescheitert: der Guard hat nichts gefunden und deshalb den Build
# abgebrochen, statt "nichts zu prüfen" zu melden.
PREV_TAG="$(git tag --list 'v*' --sort=-v:refname 2>/dev/null | grep -v "^v${CHART_VERSION}$" | head -1 || true)"

if [[ -z "$PREV_TAG" ]]; then
  skip "kein vorheriger Tag gefunden"
elif ! git cat-file -e "$PREV_TAG:$VALUES_FILE" 2>/dev/null; then
  skip "$PREV_TAG kennt $VALUES_FILE nicht"
else
  toplevel() { grep -E '^[a-zA-Z_][a-zA-Z0-9_]*:' | sed 's/:.*//' || true; }
  ALT_KEYS="$(git show "$PREV_TAG:$VALUES_FILE" 2>/dev/null | toplevel | sort -u || true)"
  NEU_KEYS="$(toplevel < "$VALUES_FILE" | sort -u || true)"
  ZUGEWACHSEN="$(comm -13 <(echo "$ALT_KEYS") <(echo "$NEU_KEYS") || true)"

  if [[ -z "$ZUGEWACHSEN" ]]; then
    ok "keine neuen Wertschlüssel gegenüber $PREV_TAG"
  else
    unsicher=0
    for k in $ZUGEWACHSEN; do
      # Kommentarzeilen ausnehmen — sonst schlaegt der Guard bei der
      # Erklaerung an, die genau vor dieser Schreibweise warnt.
      TREFFER="$(grep -rn "\.Values\.${k}\." "$TEMPLATES_DIR" 2>/dev/null | grep -vE ':[[:space:]]*#' | grep -v 'default (dict)' || true)"
      if [[ -n "$TREFFER" ]]; then
        fail "neuer Schlüssel '$k' (seit $PREV_TAG) wird direkt dereferenziert — Upgrade würde scheitern:"
        echo "$TREFFER" | sed 's/^/      /'
        unsicher=1
      fi
    done
    if [[ $unsicher -eq 0 ]]; then
      ok "neue Schlüssel gegenüber $PREV_TAG ($(echo $ZUGEWACHSEN | tr '\n' ' ')) sicher dereferenziert"
    fi
  fi
fi

section "olares dependency matches the manifest generation"

for mf in "$MANIFEST_FILE" "$ROOT_MANIFEST_FILE"; do
  [[ -f "$mf" ]] || continue
  DEP_VERSION="$(awk '/^[[:space:]]*-[[:space:]]*name:[[:space:]]*olares[[:space:]]*$/{f=1} f&&/^[[:space:]]*version:/{gsub(/.*version:[[:space:]]*/,""); gsub(/['"'"'"]/,""); print; exit}' "$mf")"
  API_VERSION="$(awk '/^apiVersion:/{gsub(/.*apiVersion:[[:space:]]*/,""); gsub(/['"'"'"]/,""); print; exit}' "$mf")"

  if [[ -z "$DEP_VERSION" ]]; then
    fail "$mf: no options.dependencies[name=olares].version found"
  elif [[ "$API_VERSION" == "v3" ]]; then
    # apiVersion=v3 verlangt genau '>=1.12.6-0' — offen nach oben, mit
    # '-0', damit Tages- und RC-Builds (1.12.6-20260327) matchen. Die
    # frühere Regel (geschlossenes Intervall) galt für v1 und ist hier
    # falsch: '<1.12.6' würde die Version aussperren, auf der die Box läuft.
    if [[ "$DEP_VERSION" == ">=1.12.6-0" ]]; then
      ok "$mf: olares dependency '>=1.12.6-0' (v3)"
    else
      fail "$mf: apiVersion=v3 requires olares dependency exactly '>=1.12.6-0', found '$DEP_VERSION'"
    fi
  elif [[ "$DEP_VERSION" == *"<"* ]]; then
    ok "$mf: olares dependency bounded ($DEP_VERSION, pre-v3)"
  else
    fail "$mf: olares dependency '$DEP_VERSION' has no upper bound — pre-v3 Market upload will 400"
  fi
done

# ---------------------------------------------------------------------------
# 1e. hostPath deployments must use strategy: Recreate
#     RollingUpdate would briefly run two pods against the same host
#     directory. The Market rejects the combination on upload with HTTP 400
#     ("can not enable rolling update with hostpath"). Cost us the v0.1.62
#     upload. Note k8s defaults to RollingUpdate when strategy is omitted,
#     so "no strategy block" is a failure, not a pass.
# ---------------------------------------------------------------------------

section "hostPath deployments use strategy: Recreate"

hostpath_ok=1
for f in "$TEMPLATES_DIR"/deployment-*.yaml; do
  grep -q "hostPath" "$f" || continue
  name="$(basename "$f")"
  if grep -qE "^[[:space:]]*type:[[:space:]]*Recreate[[:space:]]*$" "$f"; then
    ok "$name: hostPath + Recreate"
  else
    fail "$name: mounts hostPath without 'strategy: type: Recreate' — Market upload will 400"
    hostpath_ok=0
  fi
done
if [[ "$hostpath_ok" -eq 1 ]]; then
  : # all good, already reported per-file
fi

# ---------------------------------------------------------------------------
# 1f. Container resource sums must fit the manifest's declared budget
#     The Market adds up every container's requests/limits and rejects the
#     upload with HTTP 400 if a sum exceeds required*/limited* (cost us the
#     v0.1.63 upload: requests 3750m vs requiredCpu 2000m, limits 13000m vs
#     limitedCpu 6000m). Pure awk so this needs no PyYAML in CI.
# ---------------------------------------------------------------------------

section "container resources fit manifest budget"

if command -v helm >/dev/null 2>&1; then
  SUMS="$(helm template insilo olares/ -f olares/values-olares-stub.yaml 2>/dev/null | awk '
    function tocpu(v) { if (v ~ /m$/) { sub(/m$/,"",v); return v+0 } else { return v*1000 } }
    function tomem(v,  n,u) {
      if (v ~ /Gi$/) { sub(/Gi$/,"",v); return v*1024 }
      if (v ~ /Mi$/) { sub(/Mi$/,"",v); return v }
      if (v ~ /Ki$/) { sub(/Ki$/,"",v); return v/1024 }
      return v/1048576
    }
    /^[[:space:]]*resources:[[:space:]]*$/ { inres=1; mode=""; next }
    inres && /^[[:space:]]*requests:[[:space:]]*$/ { mode="req"; next }
    inres && /^[[:space:]]*limits:[[:space:]]*$/   { mode="lim"; next }
    inres && /^[[:space:]]*cpu:/ {
      v=$2; gsub(/["'"'"']/,"",v)
      if (mode=="req") rc+=tocpu(v); else if (mode=="lim") lc+=tocpu(v)
      next
    }
    inres && /^[[:space:]]*memory:/ {
      v=$2; gsub(/["'"'"']/,"",v)
      if (mode=="req") rm+=tomem(v); else if (mode=="lim") lm+=tomem(v)
      next
    }
    inres && !/^[[:space:]]*(requests|limits|cpu|memory):/ { inres=0; mode="" }
    END { printf "%d %d %d %d", rc, lc, rm, lm }
  ')"
  read -r SUM_RC SUM_LC SUM_RM SUM_LM <<< "$SUMS"

  budget() {
    # budget <manifest-key> -> value in m (cpu) or Mi (memory)
    local key="$1" raw
    raw="$(grep -E "^[[:space:]]*${key}:" "$MANIFEST_FILE" | head -1 | sed -E "s/.*${key}:[[:space:]]*([^[:space:]#]+).*/\1/")"
    case "$raw" in
      *m)  echo "${raw%m}" ;;
      *Gi) echo $(( ${raw%Gi} * 1024 )) ;;
      *Mi) echo "${raw%Mi}" ;;
      *)   echo $(( raw * 1000 )) ;;
    esac
  }

  check_sum() {
    # check_sum <label> <sum> <budget> <unit>
    if [[ "$2" -le "$3" ]]; then
      ok "$1: $2$4 <= $3$4"
    else
      fail "$1: $2$4 exceeds $3$4 — Market upload will 400"
    fi
  }

  check_sum "requests.cpu vs requiredCpu"    "$SUM_RC" "$(budget requiredCpu)"    "m"
  check_sum "limits.cpu vs limitedCpu"       "$SUM_LC" "$(budget limitedCpu)"     "m"
  check_sum "requests.memory vs requiredMem" "$SUM_RM" "$(budget requiredMemory)" "Mi"
  check_sum "limits.memory vs limitedMem"    "$SUM_LM" "$(budget limitedMemory)"  "Mi"
else
  yellow "  ! helm not installed — skipping resource-budget check"
fi

# ---------------------------------------------------------------------------
# 1g. Root containers must use a beclab image
#     The Market rejects "non-beclab image ... runs with root-equivalent
#     securityContext" (cost us the v0.1.64 upload — our init-chown used
#     plain busybox:1.36). Official Olares apps use the same init-chown
#     pattern but with docker.io/beclab/aboveos-busybox — root is allowed,
#     just not from an arbitrary image.
#     Assumes `image:` precedes `securityContext:` within a container block,
#     which holds for every template here.
# ---------------------------------------------------------------------------

section "root containers use a beclab image"

if command -v helm >/dev/null 2>&1; then
  ROOT_VIOLATIONS="$(helm template insilo olares/ -f olares/values-olares-stub.yaml 2>/dev/null | awk '
    /^[[:space:]]*-[[:space:]]*name:/ { img=""; cname=$3 }
    /^[[:space:]]*image:/ { img=$2; gsub(/["'"'"']/,"",img) }
    /^[[:space:]]*runAsUser:[[:space:]]*0[[:space:]]*$/ {
      if (img != "" && img !~ /beclab/) print cname " -> " img
    }
  ')"
  if [[ -z "$ROOT_VIOLATIONS" ]]; then
    ok "no root container on a non-beclab image"
  else
    fail "root container(s) on non-beclab image — Market upload will 400:"
    echo "$ROOT_VIOLATIONS" | sed 's/^/      /'
  fi
else
  yellow "  ! helm not installed — skipping root-image check"
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

section "image tags follow Chart.AppVersion"

# A market upgrade replays the values recorded at install time and does NOT
# adopt the new chart's defaults. A tag written into values.yaml therefore
# freezes: on 19.8.2026 the box upgraded to chart 0.1.80 and kept running
# 0.1.77 images, with every health check reporting "ok". Chart metadata does
# arrive fresh, so the tag hangs off `.Chart.AppVersion` and values.yaml
# carries a tag only to hold images back in a --chart-only release.

bad_form=0
while IFS= read -r line; do
  file="${line%%:*}"
  if [[ "$line" != *"default .Chart.AppVersion"* ]]; then
    fail "$(basename "$file"): image tag not derived from .Chart.AppVersion"
    echo "    ${line#*:}" | sed 's/^/  /'
    bad_form=1
  fi
done < <(grep -n "image:.*\.Values\.images\." "$TEMPLATES_DIR"/*.yaml 2>/dev/null || true)
[[ "$bad_form" -eq 0 ]] && ok "all workload images use '| default .Chart.AppVersion'"

PINS=$(grep -E "^[[:space:]]+tag:" "$VALUES_FILE" \
       | grep -vE 'tag:[[:space:]]*("")|('"''"')[[:space:]]*$' || true)
if [[ -z "$PINS" ]]; then
  ok "values.yaml pins nothing — images follow the chart version"
else
  PIN_VALUES=$(echo "$PINS" | sed -E "s/.*tag:[[:space:]]*[\"']?([^[:space:]\"'#]+).*/\1/" | sort -u)
  if echo "$PIN_VALUES" | grep -qx "$CHART_VERSION"; then
    fail "values.yaml pins the tag to the chart version ($CHART_VERSION) — redundant, and it freezes on the next market upgrade. Leave it empty."
  else
    yellow "  ! values.yaml pins image tags to $(echo $PIN_VALUES) — only correct for a --chart-only release"
  fi
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
