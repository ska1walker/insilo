# Plattform-Strategie

> Langfristige Vision: kaivo.studio als deutscher KI-App-Stack für Olares-Hardware.
>
> Dieses Dokument hält die übergreifende Geschäftsidee fest. Aktuell fokussieren wir
> uns ausschließlich auf **Insilo** als Erstprodukt. Diese Vision dient als Leitstern
> für Architekturentscheidungen, die langfristig mehrere Apps tragen müssen.

---

## 1. Die These

Deutscher Mittelstand braucht KI, traut aber US-Cloud-Anbietern nicht.

PLAUD, Otter, Copilot — alle landen letztlich bei OpenAI/Anthropic/Google. Für Kanzleien, Steuerberater, Ärzte, Banken und Industriebetriebe mit Compliance-Anforderungen ist das ein No-Go.

**Die Lücke:** Es gibt keine deutsche Antwort, die mehrere Geschäfts-KI-Anwendungen auf einer souveränen Infrastruktur bündelt.

**Unser Spielzug:**
1. Olares-Hardware vertreiben über aimighty.de
2. Auf dieser Box läuft ein **kaivo.studio-App-Portfolio**
3. Erste App: Insilo (Meeting-Intelligenz)
4. Weitere Apps folgen, jede löst ein spezifisches Mittelstands-Problem

---

## 2. Plattform-Ökonomie

### Warum mehrere Apps auf einer Box?

| Kennzahl                          | Eine App  | Drei Apps   |
|-----------------------------------|-----------|-------------|
| Hardware-Kosten für Kunden        | 8.000€    | 8.000€      |
| Software-Lizenz pro App/Jahr      | 12.000€   | 8.000€      |
| Umsatz pro Kunde/Jahr             | 12.000€   | 24.000€     |
| Sales-Cycle für weitere App       | -         | drastisch verkürzt |
| Customer-Lifetime-Value (5 Jahre) | 68.000€   | 128.000€    |

**Multi-App auf geteilter Hardware ist ökonomisch zwingend.**

Sobald der Kunde die Box hat (und damit das schwierigste Compliance-Gespräch geführt), ist jede weitere App ein **Upsell mit minimalem Vertriebsaufwand**.

### Cross-App-Mehrwert

Apps werden für Kunden interessanter, wenn sie miteinander reden:

- **Insilo + CallList:** Meeting-Notiz mit einem Kunden wird automatisch zur Kontakt-Historie hinzugefügt
- **Insilo + MaklerOS:** Mandantengespräch wird automatisch im Versicherungsfall hinterlegt
- **CallList + Polier:** Vertrieb sieht direkt verfügbare Lagerbestände beim Kunden vor Ort

Jede Cross-App-Integration ist ein **Lock-in-Effekt** und ein **Verkaufsargument**.

---

## 3. App-Portfolio (Vision)

### Phase Alpha: Erstausstattung (2027)

**Insilo** — Meeting-Intelligenz
- Status: in Entwicklung
- Zielgruppe: alle Branchen mit vertraulichen Gesprächen
- Burggraben: deutsche Templates, Branchen-Vokabular

**CallList** — Mobiler Vertrieb (Migration aus existierender App)
- Status: bestehende App, müsste auf Olares portiert werden
- Zielgruppe: Außendienst-Mitarbeiter
- Burggraben: Kai's eigene Domänenexpertise

### Phase Beta: Branchen-Vertikalen (2028)

**MaklerOS** — Versicherungsmakler-Suite
- Zielgruppe: Versicherungsmakler, Maklerpools
- Cross-Sell-Pfad: über Kai's hagebau-Netzwerk

**Polier** — Baustoffhändler-Tooling
- Zielgruppe: Hagebau-Gesellschafter und Wettbewerber
- Module: LV-Extraktion, Produktwissen-RAG, Lieferantenpreis-Listen

**HolzMatch** — Holzhandels-Order-Matching
- Status: Showcase-MVP existiert
- Zielgruppe: Holzgroßhandel

### Phase Gamma: Spezialisierung (2029+)

Weitere Apps abhängig von Vertriebs-Feedback. Möglich:
- **Kanzlei-Suite** (Mandatsverwaltung + Insilo-Tiefenintegration)
- **Praxis-Suite** (Arztpraxen-Doku + sprachbasierte Patientenakte)
- **Werkstatt-Suite** (Kfz/Handwerk, Auftragsverwaltung mit KI)

---

## 4. Technische Plattform-Eigenschaften

### Was alle kaivo.studio Apps gemeinsam haben

**Designsystem:** Weiß / Schwarz / Gold mit HubSpot-Tonalität (siehe `docs/DESIGN.md`). Alle Apps fühlen sich an wie eine Familie.

**Sprache:** Formelles Deutsch, Sie-Form, sachlich.

**Tech-Stack:**
- Frontend: Next.js 15 + Tailwind + shadcn/ui
- Backend: FastAPI (Python) oder Next.js Server Routes (für leichte Apps)
- Datenbank: Olares PostgreSQL (geteilt)
- Cache: Olares KVRocks (geteilt)
- Storage: Olares MinIO (geteilt)

**KI-Stack (apps-spezifisch):**
- Insilo: Whisper + Qwen 2.5 14B + BGE-M3
- Andere Apps: meist nur LLM-Anbindung, kein eigenes Whisper

**Auth:** Olares Authelia + LLDAP (Single-Sign-On für alle Apps).

### Naming Convention

Olares erfordert `^[a-z0-9]{1,30}$` für App-Namen. Verbindlich für alle kaivo-Apps:

- `insilo` ✓
- `calllist` ✓
- `maklerit` (Ersatz für MaklerOS, da Großbuchstaben verboten)
- `polier` ✓
- `holzmatch` ✓

### Inter-App-Pattern: Service Provider

Olares verlangt explizite Cross-App-Permissions. Jede Insilo-Funktion, die einer anderen kaivo-App zugänglich sein soll, ist ein **Provider-Endpoint**:

```yaml
# In Insilo's OlaresManifest.yaml
provider:
  - name: insilo-meetings-readonly
    entrance: insilo-backend
    paths:
      - "/api/v1/meetings"
      - "/api/v1/meetings/{id}/summary"
    verbs: ["GET"]

  - name: insilo-meetings-write
    entrance: insilo-backend
    paths: ["/api/v1/meetings"]
    verbs: ["POST"]
```

Andere kaivo-Apps können in ihren Manifesten diese Provider deklarieren:

```yaml
# In CallList's OlaresManifest.yaml
permission:
  provider:
    - appName: insilo
      providerName: insilo-meetings-readonly
```

**Wichtig für die Geschäftslogik:**
- Permissions sind statisch im Manifest, vom Endnutzer freigegeben
- Zur Laufzeit prüft `system-server` jede Anfrage
- Keine versteckten Datenflüsse zwischen Apps

---

## 5. Vertriebsstrategie

### Verkaufstrichter

1. **Awareness** (aimighty + kaivo.studio):
   - LinkedIn-Content über Datensouveränität in KI-Anwendungen
   - Whitepaper "DSGVO-konforme KI für Mittelstand"
   - Vorträge bei Branchenverbänden (Anwaltsverbände, Steuerberaterkammern)

2. **Erstgespräch** (aimighty-Vertrieb):
   - Demo Insilo auf eigener Test-Olares
   - Schmerzpunkt-Analyse beim Kunden
   - Compliance-Argumente (Schrems II, Betriebsrat, Schweigepflicht)

3. **Pilot** (4 Wochen):
   - Olares-Box als Leihgerät
   - 3-5 Mitarbeiter testen Insilo
   - Erfolgsmessung: Anzahl Meetings, Zeit-Ersparnis

4. **Kauf:**
   - Hardware (Olares One) + Insilo-Lizenz
   - Onboarding-Workshop
   - Hyper-Care-Phase 30 Tage

5. **Expansion** (12 Monate später):
   - "Wir haben jetzt auch CallList — wollen Sie das mit ausrollen?"
   - Cross-App-Demos
   - Bundle-Rabatte für Mehr-App-Setups

### Pricing-Strategie

**Hardware:** Olares One zum Listenpreis (mit aimighty-Marge)

**Software pro App:**
- Insilo: 800€/User/Jahr, ab 10 Usern, mit Mengenrabatten
- Weitere Apps: ca. 500-1.500€/User/Jahr je nach Komplexität

**Plattform-Bundle:** Alle aktuell verfügbaren Apps zu 30% Rabatt auf Listensumme.

**Service:** 20% des jährlichen Software-Volumens als Wartungs- und Support-Vertrag (mit SLA).

---

## 6. Was diese Vision für die jetzige Insilo-Entwicklung bedeutet

Damit Insilo später Teil eines App-Stacks sein kann, müssen wir **schon jetzt** folgendes beachten:

1. ✅ **Olares-konformer App-Name** (`insilo`, kein Bindestrich, keine Großbuchstaben)

2. ✅ **Saubere REST-API-Endpunkte**, die wir später als Provider exposen können

3. ✅ **Konsistentes Design-System** (`docs/DESIGN.md`), das auch andere Apps nutzen werden

4. ✅ **Olares-System-Middlewares nutzen** statt eigene Container für DB/Cache — sonst skaliert es nicht über mehrere Apps

5. ✅ **Multi-Tenant von Anfang an** — Orgs als oberste DB-Ebene

6. ✅ **Keine eigene Auth** — Authelia ist plattform-weit

7. ⏳ **Inter-App-Kommunikation noch NICHT bauen** — Phase 1 fokussiert sich auf Insilo-Standalone. Provider-Pattern kommt erst, wenn zweite App in Sicht.

---

## 7. Risiken und offene Fragen

### Olares-Plattform-Risiken

- **Single-Vendor-Lock-In:** Wenn Olares-Projekt pivotet oder eingestellt wird, sitzen wir auf einem nicht-portablen Stack. **Mitigation:** Wir bauen so, dass Migration auf reines Kubernetes machbar bleibt.

- **Olares-Markt-Reichweite begrenzt:** Olares ist (Stand 2026) noch klein. Wir können nicht auf Marketplace-Discovery zählen. **Mitigation:** Direktvertrieb via aimighty, Olares-Markt ist nur Distributions-Mechanismus.

- **Performance-Limits:** Olares One reicht für Insilo + 1-2 leichte Apps. Mehrere LLM-Apps brauchen größere Hardware. **Mitigation:** Hardware-Tiers anbieten (Basis / Pro / Enterprise).

### Geschäftsrisiken

- **Kein eigener Hardware-Vertrieb:** Wir hängen vollständig an aimighty. **Mitigation:** Langfristig eigene Beziehungen zum Olares-Hersteller.

- **App-Entwicklungskapazität:** Kai ist Solo-Entwickler. Mehrere Apps gleichzeitig pflegen wird schnell zur Bremse. **Mitigation:** Codebase-Konsistenz reduziert Pflegeaufwand. Spätestens bei dritter App: zweiter Entwickler nötig.

- **Vendor-Konzentration bei Kunden:** Mehrere Apps von uns = höherer Verlust-Schmerz für Kunden bei Wechsel. Aber: auch höhere Switching-Costs für uns als Lieferant, wenn Kunde wegfällt. **Mitigation:** Vertragliche SLAs und Exit-Klauseln professionell aufsetzen.

---

## 8. Erfolgsdefinition

**Phase Alpha (Ende 2027):**
- 10 zahlende Insilo-Kunden
- 1 Pilot-Kunde mit zweiter App
- 500.000€ ARR

**Phase Beta (Ende 2028):**
- 50 Insilo-Kunden
- 20 davon Multi-App-Kunden
- 2-3 Apps live im Portfolio
- 2.000.000€ ARR

**Phase Gamma (Ende 2029):**
- 150+ Kunden
- Durchschnittlich 2,5 Apps pro Kunde
- 5+ Apps live
- 8.000.000€ ARR

Diese Zahlen sind ambitioniert, aber bei einem 3-Mann-Team mit klarer Positionierung in einem unterversorgten Markt nicht unrealistisch.
