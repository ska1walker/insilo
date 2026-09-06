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
| Alle Token (Farbe, Raum, Schrift, Radien, Zustände) | `frontend/app/globals.css`, Block ganz oben |
| Tailwind-Anbindung | `frontend/tailwind.insilo.preset.js` — unverändert aus dem Paket |
| Schriften | `frontend/app/fonts/`, geladen per `next/font/local` |
| Bauteile (Knöpfe, Felder, Streifen, Tabelle) | `frontend/app/globals.css`, `@layer components` |
| Lebendes Referenzblatt | `InSilo_Design-Paket.html` aus der Lieferung |

**Regel:** Wer einen Wert ändert, ändert ihn in `globals.css` — nie am
Bauteil. Das Tailwind-Preset dupliziert keine Werte, es liest sie über
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

### Das Wappen

`components/wappen.tsx`, kein `<img>` — und **zwei Fassungen statt einer
umgefärbten**. Die Vorlagen unterscheiden sich um mehr als die Textfarbe:
auf hellem Grund ist die Wortmarke Hanseatenblau mit weißem Monogramm,
auf dunklem beides weiß. Das ist eine gestalterische Entscheidung, keine
Umfärbung — sie wird deshalb übernommen, nicht nachgerechnet.

Beide liegen im Markup, CSS zeigt die passende (`.wappen-hell` /
`.wappen-dunkel`). Ohne JavaScript, damit beim Laden nichts umspringt.

**Werden die Vorlagen ersetzt, muss das Bauteil neu erzeugt werden** —
sonst zeigt die Navigation weiter das alte Zeichen. Quellen im Repo:
`public/insilo_logo_hell.svg`, `_dunkel.svg`.

### Das App-Symbol

Aus derselben Figma-Quelle, als Vektor geholt und aus einem
1024-px-Rendering abgeleitet — kleine Größen aus einem großen verkleinert
sind schärfer als ein hochskaliertes Original. Quelle bleibt als
`icons/icon-quelle.svg` im Repo.

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

## 6. Bewegung

Animationen sind funktional, nie dekorativ. Das Paket gibt zwei Dauern
vor (`--am-dauer-kurz` 120 ms, `--am-dauer-lang` 200 ms), aber keine
Beschleunigungskurve — dafür bleibt `--ease-out` aus dem Altbestand.

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

Kachel in Sand mit Verlauf (`#D6B265`), Schild in Hanseatenblau, Monogramm
„I" in Gold. Quelle: Figma AImighty, Knoten **301:164** („Icon-Labor" ›
„Gold fuer die Anwender-Apps" › „app goldgrund I"). Der Sandgrund ist der
Ton, den die Farbtablette für **Anwender-Apps** vorsieht — er
unterscheidet sie von den Werkzeugen, die der Kunde nie sieht.

Zwei Vektorquellen unter `frontend/public/icons/`:

| Quelle | Wofür | Warum eigen |
|---|---|---|
| `icon-quelle.svg` | Olares-Kachel, PWA „any" | zeigt das Symbol wie gestaltet, mit Eckenrundung |
| `icon-maskable-quelle.svg` | Android-Maske, Apple-Touch | randlos, ohne Rundung und ohne Kante — beide Systeme runden selbst, eine mitgelieferte Rundung ergäbe einen doppelten Rand |

**Alle PNG-Größen entstehen aus diesen beiden Dateien:**

```bash
node scripts/icons.mjs
```

Eine neue Größe ist eine Zeile in `ZIELE`, kein Figma. In v0.1.68 war
`icons/` leer, während `manifest.json` drei Dateien versprach — wer die
App auf den Home-Bildschirm legte, bekam kein Symbol. Deshalb ein Skript
statt Handarbeit.

**Verkleinert wird für die Android-Maske nichts.** Das Schild reicht nur
bis 51 von 64 erlaubten Einheiten vom Mittelpunkt und liegt damit im
garantierten Innenkreis (80 % Durchmesser). Das alte Symbol trug ein
randnahes Zeichen und musste auf 78 % — dieses nicht. Wer die Vorlage
ändert, rechnet das nach, statt es zu übernehmen.

**Nicht dasselbe wie das Wappen in der Navigation.**
`components/wappen.tsx` zeigt die Wortmarke (Schild *plus* Schriftzug) aus
den Knoten 98:441/98:426 und bleibt davon unberührt.
