---
name: olares-release
description: Eine produktreife Olares-App veröffentlichen — Pfadwahl zwischen öffentlichem Markt (beclab/apps-PR), eigener Market Source und lokalem Upload, dazu die Insilo-spezifischen Lücken und der Release-Ablauf. Nutzen, wenn eine App in einen Store soll, ein Markt-Eintrag aktualisiert wird oder zu klären ist, welcher Distributionsweg trägt.
---

# Eine Olares-App veröffentlichen

> **Erst prüfen, ob die offiziellen Skills reichen.** Olares liefert
> vierzehn gepflegte Agent-Skills mit — `olares-publish` (beclab/apps-PR),
> `olares-chart` (Chart schreiben + `olares-cli chart lint`),
> `olares-market` (install/upgrade/upload), `olares-doctor` (Diagnose).
> Sie sind aktueller als alles, was hier steht. Dieser Skill deckt nur ab,
> was sie nicht wissen können: **welcher Weg für Insilo der richtige ist
> und was an Insilo dafür noch fehlt.**
>
> Installation samt Skills: `npx @olares/cli@latest install`
> Anmeldung: `olares-cli profile login --olares-id <id>`
> (Browser + Passwort, ggf. TOTP — **das macht Kai selbst**, nicht der Agent).

## 1. Die drei Wege — und welcher wann trägt

| Weg | Wie | Sichtbarkeit | Dauer | Wofür |
|---|---|---|---|---|
| **Lokaler Upload** | Market → My Olares → *Upload custom app package*, oder `olares-cli market upload <chart.tgz>` | nur diese Box | Minuten | Entwicklung, eigene Box |
| **Eigene Market Source** | Cloudflare Pages spricht die Olares-Markt-API, Box pollt alle 5 min | jede Box, die die Quelle einträgt | 1–2 Tage einmalig | **Kundenauslieferung** |
| **Öffentlicher Markt** | PR an [`beclab/apps`](https://github.com/beclab/apps), GitBot prüft mechanisch und merged automatisch | weltweit | Tage | öffentliche Produkte |

**Für Insilo ist die eigene Market Source der Weg.** Begründung, nicht
Geschmack: Insilo ist proprietär lizenziert, wird über aimighty.de
vertrieben und läuft auf Kundenboxen. Ein öffentlicher Katalogeintrag
liefert Sichtbarkeit, die wir nicht brauchen, und verlangt Listing-Material
(Screenshots, Marketing-Bilder), das den Vertriebsweg nicht abkürzt. Die
eigene Quelle gibt denselben vollständigen Installationsablauf
(`application`-CR, `ns-owner`-Label, NetworkPolicy) ohne fremde Freigabe.

**Der lokale Upload ist kein Auslieferungsweg.** Er registriert die Version
auf genau einer Box. Er ersetzt kein Deployment — siehe §3.

## 2. Voraussetzung: die App läuft schon

Der offizielle Skill sagt es deutlich, und es gilt für jeden der drei Wege:
**erst muss die App auf einer echten Box installiert sein und `running`
erreichen.** Veröffentlichen ohne bewiesene Installation verbrennt nur
GitBot-Zyklen und Vertrauen.

Für Insilo heißt das konkret — vor jedem Markt-Schritt:

- `bash scripts/check-chart.sh` grün (16 Guards, jeder aus einer echten
  Ablehnung entstanden)
- alle fünf Pods auf der Zielversion, alle fünf Health-Endpunkte `ok`
- das Feature, das die Version rechtfertigt, **gegen die laufende App**
  geprüft — nicht gegen den Diff

## 3. Reihenfolge: erst ausrollen, dann hochladen

Beim Upload von v0.1.74 gemessen: der Markt **führt** beim Bestätigen ein
`helm upgrade` aus (Revision 52 → 53). Die Pods blieben trotzdem stehen,
weil das gerenderte Ergebnis identisch war — das hochgeladene Chart trug
die Tags, die schon liefen.

Daraus die Reihenfolge, die trägt:

```bash
# 1. ausrollen, mit expliziten Tags (--reuse-values spielt sonst die ALTEN zurück)
scp dist/insilo-X.Y.Z.tgz olares@192.168.1.17:/tmp/
ssh olares@192.168.1.17 'KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
  helm upgrade insilo /tmp/insilo-X.Y.Z.tgz -n insilo-kaivostudio --reuse-values \
  --set images.frontend.tag=X.Y.Z --set images.backend.tag=X.Y.Z \
  --set images.whisper.tag=X.Y.Z --set images.embeddings.tag=X.Y.Z'

# 2. nachsehen, was WIRKLICH läuft — die Helm-Meldung genügt nicht
ssh olares@192.168.1.17 "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods \
  -n insilo-kaivostudio -o custom-columns='N:.metadata.name,I:.spec.containers[*].image'"

# 3. erst dann hochladen
olares-cli market upload dist/insilo-X.Y.Z.tgz     # oder über die Market-UI
```

Umgekehrt — erst hochladen und hoffen — hängt das Ergebnis an den
gespeicherten Helm-Werten. Genau daran ist v0.1.66 gescheitert: Chart
0.1.66 bei Images 0.1.56, Helm meldete Erfolg, der Markt zeigte die neue
Version, die Pods liefen unverändert weiter.

## 4. Was Insilo für den öffentlichen Markt noch fehlt

Nur relevant, falls der Weg doch gegangen wird. Stand v0.1.74 geprüft:

| Punkt | Ist | Soll |
|---|---|---|
| Manifest-Version | `olaresManifest.version: '0.11.0'`, kein `apiVersion` (= v2) | v3: `'0.12.0'` + `apiVersion: 'v3'` — v2 wird mit **403 `apiVersion v2 is incompatible`** abgelehnt |
| Olares-Abhängigkeit | `>=1.12.3-0,<1.12.6` | bei v3 zwingend `>=1.12.6-0` (Box läuft bereits 1.12.6) |
| `replicas` | fest `1` in fünf Deployments | `{{ .Values.workloads.<name>.replicaCount }}` + `workloadReplicas` top-level |
| Kategorien | `Productivity_v112`, `Utilities_v112`, `Productivity` | `Productivity_v112` ist abgekündigt; genau eine primäre Kategorie |
| Listing-Bilder | `featuredImage` und `promoteImage` zeigen beide auf `icon.png` | echte 1440×900-Aufnahmen; das Manifest trägt dazu seit Monaten ein TODO |
| Icon | 512×512 | öffentlicher Markt verlangt 256×256 |

**Die v3-Migration ist kein Nachmittag.** Sie berührt beide Manifeste, alle
fünf Deployments und `values.yaml`. Vorher `olares-cli chart lint` gegen
den aktuellen Stand laufen lassen — die Fehlermeldungen sind präzise und
nennen den erwarteten Wert.

## 5. Die Versionsregel

Insilo führt die Version an **vier** Stellen, Marcs Market Source an
**fünf** (dort kommt der `CHARTS`-Key `<name>-<version>.tgz` in `_lib.ts`
dazu). `scripts/release.sh X.Y.Z` hält unsere vier synchron,
`check-chart.sh` bricht bei Drift ab.

**Metadaten-only-Änderungen brauchen trotzdem einen Versionssprung.** Der
Katalog-Hash entsteht aus `ID:name:version` — Titel, Kategorien und
Beschreibungen ändern ihn nicht, also synchronisiert Olares nicht.

**Bei Insilo bleibt es bei SemVer.** Marcs Datumsschema `YY.MM.<n>` sieht
aufgeräumt aus, hat aber einen dokumentierten Defekt: die führende Null im
Monatsfeld (`26.09.81`) lässt `olares-cli market upgrade` an der
strict-semver-Prüfung scheitern — auf beiden Seiten, Ziel *und*
installierte Version. Übrig bleibt uninstall + install. Diesen Fehler
holen wir uns nicht freiwillig ins Haus.

## 6. Eigene Market Source aufsetzen

Der ausführliche, in Betrieb erprobte Weg steht in
[`docs/MARKET_SOURCE_PLAYBOOK.md`](../../../docs/MARKET_SOURCE_PLAYBOOK.md)
(Marcs Gold-Standard, August 2026). Die vier Endpunkte, die eine Quelle
sprechen muss:

```
GET  /api/v1/appstore/hash          → Katalog-Hash, Basis der Sync-Entscheidung
GET  /api/v1/appstore/info          → Liste aller Apps
POST /api/v1/applications/info      → Details (Batch), mit chartName
GET  /api/v1/applications/<n>/chart → Chart als gzip-Tarball
```

**Vor dem Abschreiben aus dem Playbook prüfen:** Marcs Konventionen sind
für Modell-Apps gedacht. Das Titelmuster `AIM <Modell> <Größe> <Aufgabe>`
gilt nicht für Produkt-Apps — in seinem eigenen Inventar heißen sie
„Wings for Hermes" und „Rewind". Insilo heißt Insilo.

**Auf Kais Box ist die AIMighty-Quelle nicht eingetragen** (gültige
Quellen: `market.olares`, `cli`, `upload`, `studio`). Sie muss zuerst
hinzugefügt werden, sonst greift `-s market.AImighty` ins Leere.

## 7. Wenn etwas klemmt

Erst `olares-doctor` (offizieller Skill) — der kennt die Laufzeitfehler.
Danach das Playbook §6/§7: Werte-Freeze bei `market upgrade`,
`raw_data`-Verklemmung (einziger Dauerfix: Quelle entfernen und neu
hinzufügen), Cloudflare-Edge-Cache, render-failed ohne Auto-Retry.

**Grundregel aus drei teuren Fehlern in diesem Repo:** eine Beschreibung
ist kein Beleg. Nicht der Commit-Message glauben, nicht dem Doc-Kommentar,
nicht der Häufigkeit einer Fundstelle — die ausführende Datei lesen und den
laufenden Zustand abfragen.
