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
„Bestand"). Drei Dinge, die eine Meeting-App braucht, kommen dort nicht
vor.

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
Modell-Download beim Erststart. Audio und Suchindex verlassen sie in
keiner Konfiguration.

Der Nachweis zeigt darum den gemessenen Zustand in drei Lagen:

| Lage | Ton | Aussage |
|---|---|---|
| alles intern | Erfolg | „Bleibt auf der Box" |
| Ziele aktiv | neutral | Anzahl und übertragene Menge |
| LLM extern | **Achtung** | „Modell extern", nennt den Anbieter |

Der dritte Fall ist der wichtigste — dort verliert ein Kunde sein
Kernversprechen, oft ohne es zu merken.

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
