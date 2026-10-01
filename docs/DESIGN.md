# Design-System

> **Insilo läuft auf dem AImighty-Designsystem.**
> Die Werte stehen nicht hier, sondern im gelieferten Paket. Dieses
> Dokument hält fest, wo Insilo davon abweicht oder es ergänzt — und
> warum.
>
> Umgestellt am 18. August 2026. Das frühere eigene System (Weiß/Schwarz/
> Gold, Lexend Deca + Inter, 8px-Raster, Anker HubSpot/aimighty/PLAUD)
> ist vollständig abgelöst. Wer es nachlesen will:
> `git show ab5b8ce~9:docs/DESIGN.md`.

---

## 1. Wo die Werte stehen

| Was | Wo |
|---|---|
| Alle Token (Farbe, Raum, Schrift, Radien, Zustände, Bewegung, Ebenen) | `frontend/app/globals.css`, Block ganz oben — **wörtlich `tokens/app.css` aus dem AImighty-CI** (seit Etappe 1 des CI-Anschlusses; welcher Stand, sagt `frontend/ci/stand.json`). Geändert wird er im CI, nie hier |
| Tailwind-Anbindung | `frontend/tailwind.insilo.preset.js` — unverändert aus dem Paket |
| Schriften | `frontend/app/fonts/`, geladen per `next/font/local` |
| Bausteine (Knopf, Feld, Karte, Leerzustand, Hinweiszeile, Tabelle, Dialog, Zeichen) | `frontend/app/globals.css`, je Abschnitt mit Kennung `[AM-…]`/`[HB-…]` — **wortgleich mit `bauteile/<KENNUNG>.css` aus dem CI**, geprüft mit `python3 frontend/ci/werkzeug/bauteile.py frontend/app/globals.css --ohne-md` |
| Insilos Eigenes (Aufnahmeknopf, Schauerfunktion, Besprechungszeile, Auswahl, Herkunft) | dieselbe Datei, Kennung `[IN-…]` (CI ABGLEICH IN-K) — bleibt in Insilo |
| Lebendes Referenzblatt | `InSilo_Design-Paket.html` aus der Lieferung |

### Stand aus dem CI

Seit dem CI-Anschluss (Oktober 2026, Etappen 1–5) ist **das CI-Repo
`ska1walker/aimighty-ci` die Quelle** für Token, Zeichen und Bausteine.

- **Ein Stand ist ein Tag `ci-YY.M.n`** im CI-Repo, gesetzt von dessen
  Action `stand.yml` nach jedem Merge, der das Paket ändert. Insilo holt
  nie `main`.
- **Die Kopie** liegt unter `frontend/ci/` (Token, Zeichen, Bausteine,
  `werkzeug/bauteile.py`) mit `stand.json` (Tag, Commit, sha256 je Datei).
  Gebaut und geprüft wird ohne Netz gegen diese Kopie.
- **Holen** beim Entwickeln, aus einem Klon des CI-Repos, aus `frontend/`:
  `node scripts/ci-holen.mjs --von ../../aimighty-ci --stand ci-YY.M.n`.
  Danach entsteht `lib/symbole.tsx` neu. Ändert sich ein Token oder
  Baustein, wird der Block in `globals.css` aus der Kopie übernommen.
- **Was wacht:** `tests/ci-stand.test.ts` (Kopie unverändert, Token-Block =
  `ci/tokens/app.css`, jeder `AM-`/`HB-` Abschnitt = `ci/bauteile/`),
  `tests/abschnitte.test.ts`, `tests/symbole.test.ts`.

**Eine Änderung** an Token, Zeichen oder gemeinsamem Baustein: im CI (PR,
mergen, neuer Stand), dann hier holen. Bleiben soll eine Abweichung nur mit
Eintrag im Abschnitt „Insilo“ der CI-`ABGLEICH.md`.

**Regel:** Wer einen Wert ändert, ändert ihn im CI — nie in
`globals.css` und nie am Bauteil. Das Tailwind-Preset dupliziert keine Werte, es liest sie über
`var(--am-*)`.

**Das Preset bleibt unverändert.** Es ist eine Kopie der Quelle. Was
angepasst werden muss, gehört in unsere `tailwind.config.ts` (dort sitzt
zum Beispiel der nötige Typ-Cast) oder als eigener Token nach
`globals.css`.

---

## 2. Die Grundzüge

**Farbe.** Hanseatenblau trägt die Fläche. Im Hellmodus handelt Blau und
Gold zeichnet aus; im Dunkelmodus handelt Gold — Blau auf Blau trägt
nicht. Diese Rollenumkehr steckt vollständig in den Token, Bauteile
merken davon nichts.

**Schrift.** Geist Sans und Geist Mono, selbst gehostet aus dem Repo.
Kein Google-CDN, auch nicht zur Bauzeit — bei einem Produkt, das
Datensouveränität verspricht, wäre ein Fremdabruf beim Bauen die falsche
Fußnote.

**Raum.** Grundeinheit 4 px mit Dichte-Multiplikator (weit 1,1 · normal
1,0 · kompakt 0,9). Vorgabe ist „weit", auf Berührung greift automatisch
„normal". Der Hebel steht als `--am-skalierung` bereit; eine Bedienung
dafür gibt es noch nicht.

**Zielgrößen.** 40 px am Zeiger, 44 px auf Berührung — ohne Ausnahme.
Auch die kleinen Knopfvarianten wachsen auf einem Telefon auf 44 px.

**Zustände.** Farbe trägt eine Aussage nie allein. Jeder Zustandsstreifen
hat ein Zeichen und einen Satz.

---

## 3. Was Insilo ergänzt

Das Paket ist aus einem Lager-Beispiel abgeleitet („3 Silos angebunden",
„Bestand"). Was eine Meeting-App braucht, kommt dort nicht vor — die
folgenden Ergänzungen schließen diese Lücken.

### Gold zeichnet die laufende Aufnahme aus

Das Paket kennt keine Farbe für „nimmt gerade auf". Sein Fehler-Rot
(`#ad3f38`) liegt zu nah am früheren Aufnahme-Rot (`#C84A3F`) — „läuft"
und „Mikrofon verweigert" wären kaum unterscheidbar gewesen.

Entscheidung: **Gold.** Eine laufende Aufnahme ist der ausgezeichnete
Zustand, und Gold ist im Paket genau dafür da. Rot bleibt dem Fehler
vorbehalten. Das Speichern tritt als Übergang in gedämpftes Grau zurück.

### `--am-gold-beschriftung`

`--am-gold-800` ist im Paket ausdrücklich als „Gold als Text **auf
Weiß**" gerechnet. Auf der dunklen Fläche kommt es auf 3,3:1 und fällt
damit unter die Lesbarkeitsschwelle von 4,5:1.

Deshalb gibt es eine semantische Stufe für Gold als Beschriftung
(Sprechernamen, aktiver Navigationseintrag, Aufnahme-Pille):

```
hell:   --am-gold-beschriftung → --am-gold-800   (4,9:1 auf Weiß)
dunkel: --am-gold-beschriftung → --am-gold-500   (7,2:1 auf der Navigationsfläche)
```

Falls AImighty dafür einen eigenen Wert vorsieht, gehört er in
`tokens/globals.css` und ersetzt diesen.

### Die Welle während der Aufnahme

Das Paket verlangt Animationen, die etwas leisten. Der Pegelverlauf unter
dem Timer zeigt deshalb das **echte Mikrofonsignal**, nicht eine
Zierschleife — er beantwortet die einzige Frage, die während einer
Aufnahme zählt: kommt Signal an. Eine erfundene Bewegung liefe auch bei
totem Mikrofon weiter.

Der Pegel ist **logarithmisch** skaliert (−60 dB bis −6 dB), nicht
linear. Ein linearer Faktor sättigt schon bei halber Aussteuerung; die
Anzeige stünde beim Sprechen dauerhaft am Anschlag und zeigte nichts
mehr. Gold, weil die laufende Aufnahme die Auszeichnung trägt.

### Die Kopfecke

Seit Etappe 6 des CI-Anschlusses (CI ABGLEICH R4, G1): **die
AImighty-Wortmarke und daneben „Insilo“** — dieselbe Kopfecke wie in jeder
AImighty-Anwendung, 240 × 56 px, Bausteine HB-MARKE und AM-HUELLE
(`components/marke.tsx`, `components/huelle.tsx`). Die Wortmarke ist
unverändert aus dem CI (`public/marke/`, siehe README dort), hell und dunkel
als zwei Dateien, das CSS zeigt die passende. Das frühere eigene Wappen mit
dem Schriftzug „insilo“ (`components/wappen.tsx`, Figma 98:441/98:426) ist
entfallen.

Insilo sucht nicht und legt nicht von überall an — die Leiste über der
Seite trägt deshalb nur die Kopfecke, auf derselben Höhe wie Rocket (G1:
„eine Kopfleiste nur, wer sucht oder anlegt; die anderen haben trotzdem
dieselbe Kopfecke“).

### Das App-Symbol

Sandgrund, Wappen und darin seit 01.10.2026 das **Mikrofon** statt des
„I" (CI R5). Quelle ist `icons/icon-quelle.svg` im Repo; alle Größen
entstehen daraus, kleine aus einem großen Rendering verkleinert — das ist
schärfer als ein hochskaliertes Original. Im Browser-Tab steht nur das
Mikrofon (CI G7). Einzelheiten unten unter „Symbol der Anwendung".

**Die maskable-Fassung wird nachgerechnet, nicht verkleinert.** Android
beschneidet App-Symbole auf beliebige Formen; garantiert sichtbar ist nur
der innere Kreis mit 80 % Durchmesser. Beim alten Symbol reichte das Zeichen
bis an den Rand und musste auf 78 % verkleinert werden. Beim heutigen
Symbol (Idee 6, Sandgrund und Wappen) liegt das Schild innerhalb des
Kreises — die Rechnung steht unten unter „Symbol der Anwendung". *(Bis zum
06.09.2026 widersprach dieser Absatz dem Abschnitt unten.)*

### Auswahlfelder

Der native Pfeil sitzt je nach Browser hart an der Kante und ignoriert
das Padding. Alle `select` tragen deshalb ein eigenes Zeichen, mit
demselben Randabstand wie der Text links, und halten rechts Platz frei,
damit lange Einträge nicht darunter laufen.

---

## 4. Die Hülle

Drei Bereiche: Navigation, Inhalt, Ablage.

**Navigation.** Wappen mit festem Klickziel zur ersten Ansicht. Der
Produktname daneben ist Beschriftung, kein Bedienelement — Insilo läuft
als einzelnes AImighty-Produkt, es gibt nichts umzuschalten.

Reihenfolge: Aufnahme, Besprechungen, Archiv, Idee — abgesetzt darunter
Einstellungen und Über. Aufnahme steht zuerst, weil es die häufigste
Handlung ist. Der primäre Knopf wandert dafür in die jeweilige Ansicht;
das System erlaubt genau eine primäre Handlung je Ansicht.

**Ablage.** Trägt Kontext zum gewählten Ding und ist ausdrücklich nie
eine zweite Inhaltsspalte. Sie erscheint nur, wo eine Ansicht sie über
`useAblage()` befüllt — sonst fällt die Spalte weg. Bei Insilo ist das
allein das Besprechungs-Detail.

**Mobil** deckt das Referenzblatt nicht ab, es zeigt nur den Zeigerfall.
Insilo ist aber primär eine Telefon-PWA, und 220 px Seitenspalte gehen
auf 375 px nicht auf. Unterhalb von 1024 px wandert die Navigation an den
unteren Rand (daumennah, mit Berücksichtigung der Safe Area), die Ablage
rutscht unter den Inhalt. Auf der Leiste ist Platz für fünf Ziele — „Über
Insilo" entfällt dort und bleibt über die Einstellungen erreichbar.

---

## 5. Der Datenschutz-Nachweis

Das Paket sieht ihn am unteren Rand der Navigation vor, **mit gemessenen
Werten — oder gar nicht**. Diese Regel ist bei Insilo keine Formalie: das
gesamte Verkaufsargument gegenüber PLAUD, Otter und Fireflies hängt
daran, dass die Aussage stimmt.

**Insilo ist nicht pauschal „0 Byte".** Drei Dinge können die Box
verlassen: das Transkript (wenn ein externer LLM-Endpunkt eingetragen
ist), fertige Protokolle (an konfigurierte Webhooks) und der einmalige
Modell-Download beim Erststart — und seit v0.1.77 die **Tonaufnahme
selbst**, wenn jemand einen externen Endpunkt für die Spracherkennung
einträgt. Das ist der schwerste der vier Fälle und steht deshalb in
allen drei Ansichten vor den anderen: wer aufnimmt, muss es vorher
wissen. Ohne Eintrag transkribiert der mitgelieferte Dienst, und die
Aufnahme bleibt, wo sie ist. Der Suchindex verlässt die Box in keiner
Konfiguration.

Der Nachweis zeigt darum den gemessenen Zustand in drei Lagen:

| Lage | Ton | Aussage |
|---|---|---|
| alles intern | Erfolg | „Bleibt auf der Box" |
| **eigene Box, öffentlicher Weg** | Erfolg | „Eigene Box", nennt den Host |
| Ziele aktiv | neutral | Anzahl und übertragene Menge |
| LLM bei Dritten | **Achtung** | „Modell extern", nennt den Anbieter |

Der letzte Fall ist der wichtigste — dort verliert ein Kunde sein
Kernversprechen, oft ohne es zu merken.

**Warum es die zweite Lage braucht:** Der clusterinterne Weg zu LiteLLM
ist versperrt (Envoy verlangt einen Authelia-Token, den ein
Server-zu-Server-Aufruf nicht hat). In der Praxis läuft das Sprachmodell
deshalb über die öffentliche Adresse derselben Box. Ohne diese
Unterscheidung würde der Nachweis dauerhaft warnen, obwohl kein Dritter
beteiligt ist — und eine Warnung, die immer steht, wird überlesen.
Entschieden wird über `OLARES_ZONE`; die Zone muss auf einer Punktgrenze
enden, sonst käme `boese<zone>` durch.

**Ist der Zustand nicht abrufbar, steht dort nichts.** Eine Zusage ohne
Beleg ist schlechter als keine. Dieselbe Regel gilt für den Block unter
dem Aufnahme-Knopf.

Technisch: `backend/app/egress.py` entscheidet, ob ein Ziel die Box
verlässt, und rät dabei nicht — was nicht nachweislich intern ist, gilt
als extern. 23 Tests decken das ab, inklusive Namen wie
`localhost.evil.example`. Ein zu Unrecht gezeigter Hinweis kostet eine
Rückfrage; eine zu Unrecht gezeigte Entwarnung kostet das Versprechen.

---

## 4a. Insilos eigene Abschnitte

Was nur Insilo hat, steht in `globals.css` unter der Kennung `IN-` (CI
`ABGLEICH.md`, IN-K) und bleibt hier. `tests/abschnitte.test.ts` verlangt,
dass jede `IN-` Kennung in dieser Tabelle steht.

| Kennung | Was |
|---|---|
| `IN-AUSWAHL` | gewählte Vorlage, Sprache, Sprecher — Fläche je Modus (IN-T2) |
| `IN-HERKUNFT` | „AImighty © Jahr“ mit Verweis auf den Hersteller, am Fuß der Navigation |
| `IN-AUFNAHME` | der runde Aufnahmeknopf, Ring und Anzeige der laufenden Aufnahme |
| `IN-IDEE` | Schauerfunktion `/idee` |
| `IN-BESPRECHUNG` | Zeile der Besprechungsliste, Zustandspille (IN-B5 offen) |

---

## 5a. Zeichen

**Ein Set für alle AImighty-Apps** (CI `ABGLEICH.md`, R2 und IN-Z1–Z3). Die
Zeichen kommen aus `marke/icons/ui/` im CI-Repo, als Kopie eines Stands
unter `frontend/ci/` (`node scripts/ci-holen.mjs --von <klon> --stand
ci-YY.M.n`). `scripts/symbole-erzeugen.mjs` schreibt daraus
`lib/symbole.tsx`; gezeichnet wird über `components/symbol.tsx` (HB-SYMBOL).

- Größen nur 16 (Text, Knöpfe), 20 (Navigation), 24 (Hauptzeichen), 40
  (Leerzustand). Der Strich ist bei jeder Größe 1,5 px.
- **Ausnahme Aufnahmeknopf** (IN-Z2, in CI `medien/app.md`): 36 px im
  120-px-Knopf, 80/96 px im großen Knopf auf `/idee` — über
  `Aufnahmezeichen`, Strich auch dort 1,5 px.
- Der Datenschutz-Hinweis zeigt `lokal`, solange nichts die Box verlässt,
  `achtung` bei einem Ziel draußen, `weitergabe` für eingetragene Ziele
  (IN-Z3). „Idee“ trägt `erkenntnis` (IN-Z4).
- **Fehlt ein Zeichen**, kommt es zuerst ins CI-Set (`werkzeug/icons-erzeugen.py`),
  dann mit einem neuen Stand hierher — nie direkt aus Lucide.
  `tests/symbole.test.ts` wacht.

---

## 6. Bewegung

Animationen sind funktional, nie dekorativ. Das CI gibt drei Dauern vor
(`--am-dauer-schnell` 120 ms, `-mittel` 200 ms, `-langsam` 320 ms) und eine
Kurve (`--am-kurve`). Der Altbestand `--ease-out`, `--duration-*` und
`--am-dauer-kurz/-lang` ist entfallen (CI `ABGLEICH.md`, T6).

Weiterhin gilt: keine Parallaxe, keine scroll-getriggerten Effekte, keine
„AI-Sparkles", keine hüpfenden Knöpfe. `prefers-reduced-motion` wird
respektiert.

---

## 7. Offen

- **Dichte-Bedienung.** Der Hebel steht, eine Einstellung dafür gibt es
  nicht. Sinnvoll erst, wenn jemand Insilo auf einem Tablet im Einsatz
  hat.
- **Radien und Randstärken** sind im Paket selbst als ungeklärt markiert
  und stehen als Vorschlag drin. Ändert sich der AImighty-Wert, ändert
  sich nur `globals.css`.
- **Prüfstand Dunkelmodus.** Kontraste sind auf der Aufnahme-Seite
  gemessen, nicht auf allen Ansichten. Dialoge, das Transkript im
  Bearbeitungsmodus und die Einstellungen sind ungeprüft.
- **Byte-Anzeige.** `webhook_deliveries.request_bytes` zählt erst seit
  Migration 0014; ältere Zustellungen tragen NULL und bleiben aus der
  Summe heraus.

---

## Symbol der Anwendung

Kachel in Sand mit Verlauf (`#D6B265`), Schild in Hanseatenblau, darin
**das Zeichen der Anwendung: das Mikrofon** (Lucide `mic`, 1.31.0) als
goldene Linie. Der Sandgrund ist der Ton, den die Farbtablette für
**Anwender-Apps** vorsieht — er unterscheidet sie von den Werkzeugen, die
der Kunde nie sieht. Verbindlich: `medien/app.md` im CI-Repo, Abschnitte
„App-Icons — die Kacheln" und „Im Browser-Tab — nur das Zeichen".

**Zeichen statt Buchstabe** — entschieden am 01.10.2026 (CI, ABGLEICH.md
**R5**, Kai mit Marc; Figma AImighty, „Icon-Labor", Abschnitt „0 — Icon-Set
(final)"). Mit Buchstaben hätten Relay und Rocket beide ein „R" getragen.
Bis dahin trug Insilo das Monogramm „I" (Figma-Knoten 301:164; Sandgrund
und Wappen stammen unverändert von dort). Gezeichnet „wie Rewind":

- Lucide-Zeichen auf 24er-Raster, um 1,4 skaliert, mittig bei (80 | 78,5)
  der 160er-Kachel — im SVG `translate(63.2 61.7) scale(1.4)`;
- Strich 3,4 auf der Kachel (2,43 im 24er-Raster), runde Enden, keine
  Füllung;
- Strich im Goldverlauf `#dfc387 → #b89957`, von oben nach unten über das
  Zeichen (y 2 → 22 im 24er-Raster).

Verlauf und Glanz sind **nur auf der Kachel** erlaubt (die einzige Ausnahme
vom Verlaufsverbot); die Kachelfarben sind keine Token.

Drei Vektorquellen unter `frontend/public/icons/`:

| Quelle | Wofür | Warum eigen |
|---|---|---|
| `icon-quelle.svg` | Olares-Markt (`icon.png`, `olares/icon-256.png`), PWA „any" | zeigt das Symbol wie gestaltet, mit Eckenrundung |
| `icon-maskable-quelle.svg` | Android-Maske, Apple-Touch | randlos, ohne Rundung und ohne Kante — beide Systeme runden selbst, eine mitgelieferte Rundung ergäbe einen doppelten Rand |
| `tab.svg` | Favicon im Browser-Tab | nur das Mikrofon, ohne Kachel und Wappen (siehe unten) |

**Im Browser-Tab nur das Zeichen** (CI, ABGLEICH.md **G7**, 01.10.2026).
Bei 16 und 32 px wäre die Kachel ein goldener Punkt mit blauem Fleck, und
alle AImighty-Apps sähen gleich aus. `tab.svg` zeichnet das Mikrofon auf
dem 24er-Raster mit Strich 2,4, runden Enden, ohne Füllung; die Farbe
richtet sich per `@media (prefers-color-scheme: dark)` **in der SVG** nach
der Tableiste — hell `#8c6c1f` (Gold 800), dunkel `#caa960` (Gold 500).
Safari nimmt kein SVG-Favicon und bekommt `tab-32.png` in `#b08a3e`. Die
Kachel bleibt für Home-Bildschirm (Apple-Touch), Manifest und Markt.

Eingebunden werden Favicon und Apple-Touch als `<link>` im `<head>` von
`app/layout.tsx` — **nie als `app/icon.*` und nie über `metadata.icons`**:
Dann rendert Next 15.5 eine Marke `<meta name="«nxt-icon»">`, die beim
Streamen stehen bleiben kann, und der Browser meldet React #418 (in Rocket
gefunden). Das Manifest nennt weiter die Kachel.

**Tab-Titel: zuerst die Seite, dann „Insilo"** (G7), etwa „Aufnahme ·
Insilo". Das Root-Layout setzt `title: { default: "Insilo", template:
"%s · Insilo" }`; eine Seite gibt als `metadata.title` nur ihren eigenen
Namen an, nie „· Insilo" dazu.

**Alle PNG-Größen entstehen aus diesen Dateien:**

```bash
node scripts/icons.mjs
```

Das schreibt `icon.png` (512, Markt-Kachel in der Wurzel, auf die das
`OlaresManifest` zeigt), `olares/icon-256.png`, `icons/icon-512/192/96.png`,
`icons/icon-maskable-512.png`, `icons/apple-touch-icon.png` (180, deckend)
und `icons/tab-32.png`. Ändert sich das Zeichen, werden **alle** neu
erzeugt — nie eines von Hand. Eine neue Größe ist eine Zeile in `ZIELE`,
kein Figma. In v0.1.68 war `icons/` leer, während `manifest.json` drei
Dateien versprach — wer die App auf den Home-Bildschirm legte, bekam kein
Symbol. Deshalb ein Skript statt Handarbeit.

**Verkleinert wird für die Android-Maske nichts.** Das Schild reicht nur
bis 51 von 64 erlaubten Einheiten vom Mittelpunkt und liegt damit im
garantierten Innenkreis (80 % Durchmesser). Das alte Symbol trug ein
randnahes Zeichen und musste auf 78 % — dieses nicht. Wer die Vorlage
ändert, rechnet das nach, statt es zu übernehmen.

**Nicht dasselbe wie die Kopfecke.** Dort steht die AImighty-Wortmarke
aus dem CI (`components/marke.tsx`); sie bleibt davon unberührt.
