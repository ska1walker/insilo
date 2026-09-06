#!/usr/bin/env bash
#
# Baut die Markt-Bilder aus den Rohaufnahmen in markt/roh/.
#
# Die Rohaufnahmen entstehen aus einer laufenden Insilo-Instanz mit
# Schau-Daten (markt/README.md erklärt, wie). Sie liegen im Repo, damit
# ein Neubau der Tafeln — anderer Text, andere Reihenfolge — keine
# Demo-Umgebung braucht.
#
#   bash scripts/markt-bilder.sh
#
# Ergebnis: markt/aufmacher.png und markt/0N-*.png, je 1920×1080.

set -euo pipefail

WURZEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKT="$WURZEL/markt"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

if [[ ! -x "$CHROME" ]]; then
  echo "Chrome nicht gefunden: $CHROME" >&2
  echo "Pfad über CHROME=… setzen." >&2
  exit 1
fi

# --allow-file-access-from-files: sonst verweigert Chrome die Schrift aus
# frontend/app/fonts/ — file:// gilt sonst als fremde Herkunft, und die
# Tafel fiele stumm auf die Systemschrift zurück.
schiessen() {
  local url="$1" ziel="$2"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --force-device-scale-factor=1 \
    --window-size=1920,1080 --virtual-time-budget=6000 \
    --screenshot="$ziel" "$url" >/dev/null 2>&1
  echo "  $(basename "$ziel")"
}

# Die Beschriftung gehört zum Bild, nicht in eine zweite Liste: wer eine
# Tafel umbenennt, ändert genau diese Zeile.
#
# Format: Datei|Marke|Satz. Der Satz muss einzeilig bleiben — zwei Zeilen
# schieben den Rahmen unter die Bildkante.
TAFELN=(
  "01-besprechungen|besprechungen|Besprechungen|Jede Aufnahme mit Zustand, Dauer und Etikett — auf einen Blick"
  "02-detail|detail|Transkript & Zusammenfassung|Die Zusammenfassung folgt Ihrer Vorlage, nicht umgekehrt"
  "03-protokoll|protokoll|Protokoll|Wer hat wann was geändert oder ausgeleitet"
  "04-datenschutz|datenschutz|Datenschutz-Nachweis|Gemessen statt versprochen: was diese Box verlassen hat"
  "05-papierkorb|papierkorb|Papierkorb|Löschen ist umkehrbar — bis die Frist abläuft"
)

kodieren() {
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

echo "Markt-Bilder:"
schiessen "file://$MARKT/vorlagen/aufmacher.html" "$MARKT/aufmacher.png"

for zeile in "${TAFELN[@]}"; do
  IFS='|' read -r datei roh marke satz <<<"$zeile"
  if [[ ! -f "$MARKT/roh/$roh.png" ]]; then
    echo "  fehlt: markt/roh/$roh.png" >&2
    exit 1
  fi
  url="file://$MARKT/vorlagen/tafel.html?kicker=$(kodieren "$marke")"
  url+="&titel=$(kodieren "$satz")&bild=$(kodieren "../roh/$roh.png")"
  schiessen "$url" "$MARKT/$datei.png"
done

echo
echo "Die Adressen im OlaresManifest zeigen auf raw.githubusercontent.com —"
echo "die Bilder wirken erst, wenn sie auf main gepusht sind."
