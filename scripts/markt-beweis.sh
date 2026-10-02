#!/usr/bin/env bash
# Beweist einen Markt-Eintrag lokal mit wrangler, bevor er in Marcs Repo geht
# (nach Rockets scripts/markt-beweis.sh; Skill olares-release, §6 Schritt 4):
#   - /api/v1/appstore/hash antwortet,
#   - /api/v1/applications/insilo/chart liefert das Chart byte-gleich,
#   - /api/v2/applications/insilo nennt Version und chartName.
#
#   bash scripts/markt-beweis.sh <markt-klon> <version> <sha256 des Charts>
set -euo pipefail
MARKT="$1"; V="$2"; SHA="$3"; PORT="${PORT:-8788}"
cd "$MARKT"
[ -d node_modules ] || npm ci --silent
# Eigene Prozessgruppe: wrangler startet workerd als Kind, das sonst bleibt.
setsid npx wrangler pages dev functions --port "$PORT" > wrangler.log 2>&1 &
WR=$!
trap 'kill -- -$WR 2>/dev/null || true' EXIT
for _ in $(seq 1 90); do curl -sf "localhost:$PORT/api/v1/appstore/hash" >/dev/null && break; sleep 1; done
curl -sf "localhost:$PORT/api/v1/appstore/hash" | grep -q '"hash"' || { tail -30 wrangler.log; echo "hash antwortet nicht"; exit 1; }
IST=$(curl -sf "localhost:$PORT/api/v1/applications/insilo/chart" | sha256sum | cut -d' ' -f1)
[ "$IST" = "$SHA" ] || { echo "Chart weicht ab: $IST statt $SHA"; exit 1; }
curl -sf "localhost:$PORT/api/v2/applications/insilo" | python3 -c "
import json, sys
s = json.dumps(json.load(sys.stdin))
for soll in ('\"chartName\": \"insilo-$V.tgz\"', '\"version\": \"$V\"'):
    assert soll in s, 'fehlt: ' + soll
"
rm -f wrangler.log
echo "bewiesen: insilo $V, Chart sha256 $SHA"
