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
> **Bereits installiert** (19.8.2026): CLI v1.12.6 und zwölf Skills unter
> `~/.claude/skills/olares-*`. Neu aufsetzen mit
> `npx @olares/cli@latest install`; scheitert die globale Installation an
> `/usr/local`, npm auf ein Nutzer-Präfix umstellen
> (`npm config set prefix ~/.npm-global`) statt `sudo` zu benutzen.
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

## 4. Das Manifest steht auf v3 — und warum das nötig war

Insilos Manifest war bis v0.1.75 Schema `0.11.0` ohne `apiVersion` (also
v2). Dazu zwei Korrekturen an dem, was hier vorher stand:

**Der offizielle Validator lehnt v2 nicht ab.** `olares-cli chart lint`
meldete für das v2-Chart `OK`, auch mit `--with-rbac
--with-security-context`. Die Behauptung „v2 wird mit 403 abgelehnt" kam
aus fremden Notizen und traf auf uns nicht zu.

**Der harte Grund war ein anderer:** unser Olares-Pin lautete
`>=1.12.3-0,<1.12.6` und sperrte damit **genau die Version aus, auf der
die Box läuft** (1.12.6). Aufgefallen ist das erst beim Vergleich mit
hermeswebui — einer App, die aus derselben Markt-Quelle auf dieselbe Box
installiert wird und `apiVersion: v3` mit `>=1.12.6-0` trägt.

Die Migration (v0.1.76) umfasste:

| Was | Von | Auf |
|---|---|---|
| Schema | `0.11.0`, kein `apiVersion` | `0.12.0` + `apiVersion: 'v3'` |
| Olares-Pin | `>=1.12.3-0,<1.12.6` | `>=1.12.6-0` |
| Replikate | fest `1` in fünf Templates | `workloadReplicas` + `.Values.workloads.<n>.replicaCount` |
| `permission.provider` | LiteLLM-Block | entfällt — ab 0.12.0 unzulässig |
| `OLARES_USER`-Env | im Backend-Deployment | entfällt — v3 verbietet das Präfix in Chart-Dateien |

**Drei Fallstricke, die dabei Zeit kosten:**

1. Vier unserer fünf Workloads haben einen Bindestrich im Namen. Helms
   Punktsyntax erreicht solche Schlüssel nicht — es muss
   `{{ (index .Values.workloads "insilo-backend").replicaCount }}` heißen.
2. Der Prüfer sucht die Zeichenkette `OLARES_USER` im **Dateitext**. Sie
   darf auch in keinem Kommentar mehr stehen.
3. `olares-cli chart lint` verlangt Ordnername == Chart-Name. Unser Ordner
   heißt `olares/`, das Chart `insilo` — deshalb immer **das gepackte
   Chart** prüfen, nie den Ordner.

Der Guard „olares dependency is a closed range" in `check-chart.sh` war
nach der Migration falsch: er stammte aus der v0.1.61-Ablehnung, die für
`apiVersion=v1` galt. Er kennt jetzt die Generation und verlangt bei v3
exakt `>=1.12.6-0`.

## 4a. Beim Ausrollen: `--reuse-values` verschluckt neue Schlüssel

Bekannt war, dass `--reuse-values` alte **Image-Tags** zurückspielt. Der
Umkehrfall kam mit v0.1.76 dazu: Helm merged bei `--reuse-values` die
**Vorgabewerte des neuen Charts nicht**. Ein Schlüssel, den das Chart erst
in diesem Release bekommt, fehlt dann schlicht:

```
Error: UPGRADE FAILED: ... at <index .Values.workloads "insilo-worker">:
error calling index: index of untyped nil
```

Helm 3.9 auf der Box kennt `--reset-then-reuse-values` noch nicht, also
müssen die neuen Schlüssel per `--set` mit. `scripts/release.sh` gibt den
vollständigen Befehl aus.

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

**Der Zugriff aufs Repo ist READ, nicht write.** Die HANDOFF-Notiz „Kai
hat Schreibzugriff" stimmt nicht mehr (`gh api repos/bayerhazard/aimighty-market`
meldet `push: false`). Der in §4.4 des Playbooks beschriebene Weg —
committen und pushen — steht damit nicht offen; es bleibt Fork + PR.

**So wurde Insilo eingereicht** (19.8.2026,
[PR #1](https://github.com/bayerhazard/aimighty-market/pull/1)):

```bash
# 1. Chart bauen und prüfen
olares-cli chart lint dist/insilo-X.Y.Z.tgz --with-rbac --with-security-context

# 2. frisches base64 — nie ein altes wiederverwenden
base64 -i dist/insilo-X.Y.Z.tgz | tr -d '\n' > /tmp/b64.txt

# 3. Eintrag in functions/_apps.ts + Schlüssel "insilo-X.Y.Z.tgz" in _lib.ts

# 4. lokal beweisen, bevor irgendetwas rausgeht
npx wrangler pages dev functions --port 8788
#    /appstore/info      → App gelistet?
#    /applications/info  → chartName + i18n["en-US"].{metadata.title,spec.fullDescription}?
#    /applications/insilo/chart → 200, und die Bytes sha256-gleich mit dem Paket?
#    /appstore/hash      → Hash bewegt sich? Sonst synchronisiert Olares nicht.
```

Schritt 4 ist der wichtige. Alle vier Endpunkte lassen sich vollständig
lokal beweisen — es gibt keinen Grund, das erst am Live-Katalog zu
merken.

## 7. Wenn etwas klemmt

Erst `olares-doctor` (offizieller Skill) — der kennt die Laufzeitfehler.
Danach das Playbook §6/§7: Werte-Freeze bei `market upgrade`,
`raw_data`-Verklemmung (einziger Dauerfix: Quelle entfernen und neu
hinzufügen), Cloudflare-Edge-Cache, render-failed ohne Auto-Retry.

**Grundregel aus drei teuren Fehlern in diesem Repo:** eine Beschreibung
ist kein Beleg. Nicht der Commit-Message glauben, nicht dem Doc-Kommentar,
nicht der Häufigkeit einer Fundstelle — die ausführende Datei lesen und den
laufenden Zustand abfragen.
