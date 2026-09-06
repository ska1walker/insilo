# Markt-Bilder

Was der Olares-Markt neben der Beschreibung zeigt: ein Aufmacher und fünf
Tafeln. Die Adressen stehen in `OlaresManifest.yaml` unter `spec.featuredImage`
und `spec.promoteImage` und zeigen auf `raw.githubusercontent.com` — die
Bilder wirken erst, wenn sie auf `main` liegen.

```
markt/
├── aufmacher.png        featuredImage, 1920×1080
├── 0N-*.png             promoteImage, 1920×1080
├── roh/                 die nackten Aufnahmen, 2880×1800 (1440×900 @2×)
└── vorlagen/            die zwei HTML-Seiten, aus denen gerendert wird
```

## Neu bauen

```bash
bash scripts/markt-bilder.sh
```

Das rendert Aufmacher und Tafeln aus `vorlagen/` neu — Text, Reihenfolge
und Beschriftung stehen im Skript, die Bildinhalte kommen aus `roh/`. Für
eine andere Beschriftung braucht es **keine** Demo-Umgebung; deshalb liegen
die Rohaufnahmen im Repo.

Die Vorlagen laden die Geist-Schriften aus `frontend/app/fonts/` und das
Wappen aus `frontend/public/icons/icon-quelle.svg`. Ändert sich das Icon,
ändert sich der Aufmacher beim nächsten Lauf mit.

## Rohaufnahmen neu machen

Nur nötig, wenn sich die Oberfläche ändert. Es braucht eine laufende
Instanz mit vorzeigbaren Daten — **keine echten Kundendaten**, die Bilder
gehen in einen öffentlichen Markt.

1. Datenbank anlegen und die Migrationen einspielen:

   ```bash
   createdb insilo_schau
   for f in supabase/migrations/*.sql; do psql -d insilo_schau -f "$f"; done
   ```

   Ohne pgvector auf dem Entwicklungsrechner scheitern die
   `vector`-Spalten. Für die Bilder reicht es, sie durch `text` zu
   ersetzen — die Ansichten, die fotografiert werden, lesen sie nicht.

2. Erfundene Daten einspielen: eine Organisation, ein Nutzer mit
   `olares_username`, fünf Besprechungen mit Etiketten, ein Transkript
   und eine Zusammenfassung, zwei gelöschte Besprechungen für den
   Papierkorb, ein Dutzend Zeilen in `audit_log` für das Protokoll.
   `supabase/seed.sql` ist der Ausgangspunkt; die Namen müssen
   offensichtlich erfunden sein („Kanzlei Beispiel & Partner",
   „Musterbau GmbH").

   Beim Schreiben in Tabellen mit erzwungener Zeilensicherheit vorher
   `select set_config('app.dienst', '1', false);` setzen — sonst weist
   die Regel den `insert` ab.

3. Backend und Frontend starten. Das Frontend muss auf **Port 3000**
   laufen, sonst weist die CORS-Regel des Backends es ab. Für die
   Aufnahmen den Produktionsbau nehmen (`npm run build && npx next start
   -p 3000`), nicht den Entwicklungsserver — der blendet Hinweise ein.

4. Aufnehmen, je Ansicht:

   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
     --headless=new --disable-gpu --hide-scrollbars \
     --force-device-scale-factor=2 --window-size=1440,900 \
     --virtual-time-budget=9000 \
     --screenshot=markt/roh/besprechungen.png \
     "http://localhost:3000/besprechungen"
   ```

   `--force-device-scale-factor=2` gibt 2880×1800 — die Tafel skaliert
   herunter, und die Schrift bleibt scharf.

5. Danach die Schau-Datenbank wegwerfen (`dropdb insilo_schau`).

Die Seitenleiste klebt oben (`position: sticky`). Eine hohe Aufnahme
(`--window-size=1440,2400`) und ein Zuschnitt daraus zerschneidet sie
deshalb — was weiter unten auf einer Seite steht, gehört auf eine eigene
Tafel, nicht in einen Ausschnitt.
