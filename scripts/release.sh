#!/usr/bin/env bash
# Cut a new Insilo release in one command.
#
# Walks the version-bump → regen-migrations → check → package → commit →
# tag → push → copy-to-Downloads chain. Aborts before the destructive
# steps (commit, tag, push) and asks for confirmation by default.
#
# Usage:
#     scripts/release.sh <new-version> [options]
#
# Examples:
#     scripts/release.sh 0.1.18
#         Bump everything (Chart, OlaresManifest, image tags) to 0.1.18.
#         Default — assumes you changed code, so a new image is wanted.
#
#     scripts/release.sh 0.1.18 --chart-only
#         Bump chart + manifest only. Image tags stay where they are.
#         Use when only the chart YAML changed (e.g. tweaked Helm template,
#         re-inlined SQL) — saves the ~3-minute GH Actions image build.
#
#     scripts/release.sh 0.1.18 -m "feat: per-org settings + retry"
#         Custom commit message. Default is "release: vX.Y.Z".
#
#     scripts/release.sh 0.1.18 --dry-run
#         Show every file mutation, but make none.
#
#     scripts/release.sh 0.1.18 --no-push
#         Stop after creating the local commit + tag. Useful for review.
#
#     scripts/release.sh 0.1.18 --yes
#         Skip the "ready to push?" prompt. CI/scripting only.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CHART_FILE="olares/Chart.yaml"
MANIFEST_FILE="olares/OlaresManifest.yaml"
VALUES_FILE="olares/values.yaml"

# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

NEW_VERSION=""
CHART_ONLY=0
DRY_RUN=0
NO_PUSH=0
ASSUME_YES=0
MESSAGE=""

while (( $# > 0 )); do
  case "$1" in
    -h|--help)
      sed -n '3,30p' "$0"; exit 0 ;;
    --chart-only)   CHART_ONLY=1; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    --no-push)      NO_PUSH=1; shift ;;
    -y|--yes)       ASSUME_YES=1; shift ;;
    -m|--message)
      MESSAGE="$2"; shift 2 ;;
    -*)
      echo "unknown flag: $1" >&2; exit 2 ;;
    *)
      if [[ -z "$NEW_VERSION" ]]; then NEW_VERSION="$1"
      else echo "unexpected positional arg: $1" >&2; exit 2; fi
      shift ;;
  esac
done

if [[ -z "$NEW_VERSION" ]]; then
  sed -n '3,30p' "$0"; exit 2
fi

if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: version must be semver X.Y.Z (got: $NEW_VERSION)" >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

bold()   { printf "\033[1m%s\033[0m\n" "$*"; }
dim()    { printf "\033[2m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
step()   { printf "\n\033[1;34m▸ %s\033[0m\n" "$*"; }

run() {
  if (( DRY_RUN )); then
    dim "    (dry-run) $*"
  else
    eval "$@"
  fi
}

# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------

step "preflight"

# Must be on main.
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  red "  ✗ not on main (currently: $CURRENT_BRANCH)"; exit 1
fi
green "  ✓ on main"

# Working-tree changes are allowed — we'll fold them into the release
# commit. Most releases ship together with a one-or-two-file code fix
# that triggered the bump; forcing a separate pre-release commit is
# annoying.
PENDING_CHANGES=0
if ! git diff-index --quiet HEAD --; then
  PENDING_CHANGES=1
  yellow "  ! tracked files have uncommitted changes (will be folded into the release commit):"
  git diff --stat | sed 's/^/      /'
fi
UNTRACKED="$(git ls-files --others --exclude-standard | grep -v '^insilo_new/' || true)"
if [[ -n "$UNTRACKED" ]]; then
  PENDING_CHANGES=1
  yellow "  ! untracked files (will be staged into the release commit):"
  echo "$UNTRACKED" | sed 's/^/      /'
fi
if (( PENDING_CHANGES )); then
  if (( ! ASSUME_YES )); then
    printf "    fold these into v%s? [y/N] " "$NEW_VERSION"
    read -r ans; [[ "$ans" == "y" ]] || exit 1
  fi
else
  green "  ✓ working tree clean"
fi

# Versions must match expectation.
CURRENT_VERSION="$(grep -E '^version:' "$CHART_FILE" | awk '{print $2}')"
if [[ "$CURRENT_VERSION" == "$NEW_VERSION" ]]; then
  red "  ✗ new version $NEW_VERSION equals current — nothing to bump"; exit 1
fi
# Lexical-ish check (not strict semver compare; good enough for our linear bumps).
if [[ "$NEW_VERSION" < "$CURRENT_VERSION" ]]; then
  yellow "  ! new version $NEW_VERSION sorts BEFORE current $CURRENT_VERSION — downgrade?"
  if (( ! ASSUME_YES )); then
    printf "    proceed anyway? [y/N] "; read -r ans; [[ "$ans" == "y" ]] || exit 1
  fi
fi
green "  ✓ bumping $CURRENT_VERSION → $NEW_VERSION"

# Tag must not exist.
if git rev-parse "v$NEW_VERSION" >/dev/null 2>&1; then
  red "  ✗ git tag v$NEW_VERSION already exists"; exit 1
fi
green "  ✓ tag v$NEW_VERSION available"

# ---------------------------------------------------------------------------
# Mutate files
# ---------------------------------------------------------------------------

step "bump versions"

# Chart.yaml — version + appVersion
run "sed -i.bak -E 's/^version:[[:space:]]+[0-9.]+/version: $NEW_VERSION/' '$CHART_FILE'"
run "sed -i.bak -E 's/^appVersion:[[:space:]]+\"[0-9.]+\"/appVersion: \"$NEW_VERSION\"/' '$CHART_FILE'"
green "  ✓ $CHART_FILE: version + appVersion → $NEW_VERSION"

# OlaresManifest.yaml — metadata.version + spec.versionName
run "sed -i.bak -E 's/^([[:space:]]+)version:[[:space:]]+[0-9.]+/\\1version: $NEW_VERSION/' '$MANIFEST_FILE'"
run "sed -i.bak -E 's/^([[:space:]]+)versionName:[[:space:]]+'\\''[0-9.]+'\\''/\\1versionName: '\\'$NEW_VERSION\\''/' '$MANIFEST_FILE'"
green "  ✓ $MANIFEST_FILE: metadata.version + spec.versionName → $NEW_VERSION"

if (( CHART_ONLY )); then
  yellow "  ! --chart-only: image tags in values.yaml unchanged"
  IMAGE_TAGS_BUMPED=0
else
  run "sed -i.bak -E 's/^([[:space:]]+tag:)[[:space:]]+[0-9.]+/\\1 $NEW_VERSION/' '$VALUES_FILE'"
  green "  ✓ $VALUES_FILE: all image tags → $NEW_VERSION"
  IMAGE_TAGS_BUMPED=1
fi

# Clean up sed-backup files.
if (( ! DRY_RUN )); then
  rm -f "$CHART_FILE.bak" "$MANIFEST_FILE.bak" "$VALUES_FILE.bak"
fi

# ---------------------------------------------------------------------------
# Regen migrations (idempotent — safe even if no schema changed)
# ---------------------------------------------------------------------------

step "regenerate migrations ConfigMap"
run "python3 scripts/regen-migrations.py >/dev/null"
green "  ✓ olares/files/ + configmap-migrations.yaml regenerated"

# ---------------------------------------------------------------------------
# Validate (the codified Phase-4 lessons)
# ---------------------------------------------------------------------------

step "scripts/check-chart.sh"
if (( DRY_RUN )); then
  dim "    (dry-run) bash scripts/check-chart.sh"
else
  if ! bash scripts/check-chart.sh; then
    red "✗ check-chart failed — aborting before any git operations"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# helm package
# ---------------------------------------------------------------------------

step "helm package"
run "rm -f dist/insilo-$NEW_VERSION.tgz"
run "helm package olares/ -d dist/ >/dev/null"
green "  ✓ dist/insilo-$NEW_VERSION.tgz"

# ---------------------------------------------------------------------------
# Diff summary + confirmation
# ---------------------------------------------------------------------------

step "summary"
if (( ! DRY_RUN )); then
  echo
  git --no-pager diff --stat
  echo
fi
bold "  release      : v$NEW_VERSION"
bold "  image tags   : $( ((IMAGE_TAGS_BUMPED)) && echo "bumped (GH Actions will build)" || echo "unchanged (chart-only)" )"
bold "  chart        : dist/insilo-$NEW_VERSION.tgz"
bold "  next step    : commit, tag, push$( ((NO_PUSH)) && echo " (local only — --no-push)" )"

if (( DRY_RUN )); then
  yellow "\n  --dry-run: no changes were made; bailing out before commit/push"
  # Roll back the file edits we just `sed`-applied. (--dry-run is honored by
  # `run`, so we already skipped them — nothing to roll back.)
  exit 0
fi

if (( ! ASSUME_YES )); then
  printf "\n  proceed with commit + tag$( ((NO_PUSH)) || echo " + push" )? [y/N] "
  read -r ans
  if [[ "$ans" != "y" ]]; then
    yellow "  aborted — files have been edited; run 'git checkout -- .' to undo"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Commit + tag + push
# ---------------------------------------------------------------------------

step "git commit + tag"
COMMIT_MSG="${MESSAGE:-release: v$NEW_VERSION}"

git add olares/ supabase/ 2>/dev/null || true
# Anything else changed (eg. backend code) the user staged earlier? Re-add to be safe.
git add -A

git commit -m "$COMMIT_MSG"
git tag "v$NEW_VERSION" -m "Insilo v$NEW_VERSION"
green "  ✓ committed and tagged"

if (( NO_PUSH )); then
  yellow "  ! --no-push: stopping here. To push later:"
  echo "      git push origin main && git push origin v$NEW_VERSION"
  exit 0
fi

step "git push"
git push origin main
git push origin "v$NEW_VERSION"
green "  ✓ pushed main + v$NEW_VERSION"

# ---------------------------------------------------------------------------
# Copy chart to ~/Downloads for the Market UI upload
# ---------------------------------------------------------------------------

step "copy chart for Market UI"
cp "dist/insilo-$NEW_VERSION.tgz" "$HOME/Downloads/"
green "  ✓ ~/Downloads/insilo-$NEW_VERSION.tgz"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

printf "\n"
bold "─── released v$NEW_VERSION ───────────────────────────────────────────"
if (( IMAGE_TAGS_BUMPED )); then
  echo "  GH Actions is building 4 images at ghcr.io/ska1walker/insilo-*:$NEW_VERSION."
  echo "  Watch:    gh run watch \$(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
else
  echo "  No image rebuild needed (chart-only)."
fi
echo
echo "  Box update — for a minor patch, helm upgrade in place:"
echo "    scp dist/insilo-$NEW_VERSION.tgz olares@192.168.112.125:/tmp/"
echo "    ssh olares@192.168.112.125 'helm upgrade insilo /tmp/insilo-$NEW_VERSION.tgz \\"
echo "        -n insilo-kaivostudio --reuse-values'"
echo
echo "  Or for a clean reinstall (DB schema / image tag / volume change):"
echo "    Market UI → uninstall → Upload custom chart → ~/Downloads/insilo-$NEW_VERSION.tgz"
