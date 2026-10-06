# Insilo — Projekt-Briefing für Claude Code

> **Produkt:** Insilo — datensouveräne Meeting-Intelligenz für deutschen Mittelstand
> **Maintainer:** Kai Böhm (kaivo.studio)
> **Vertrieb:** über aimighty.de
> **Plattform:** Olares OS (Kubernetes-basiert)
> **Status:** Phase 1 — MVP-Setup
> **Letzte Aktualisierung:** 19. August 2026 (v0.1.81)

---

## Was wir bauen

**Insilo** ist eine On-Premise-Lösung für Meeting-Aufnahme, Transkription und KI-gestützte Zusammenfassung. Sie läuft komplett auf einer Olares-Box im Serverraum des Kunden.

**Kernversprechen:** In der Vorgabe verlässt nichts die Box — Aufnahme, Transkription und Suchindex laufen vollständig darauf. Wer bewusst einen externen Endpunkt einträgt (Sprachmodell oder Spracherkennung), sieht im Datenschutz-Nachweis gemessen, was dorthin geht. Der Suchindex bleibt in jeder Konfiguration auf der Box.

**Zielsegment:** Kanzleien, Steuerberatungen, Beratungen, Industrie-Mittelstand mit Compliance-Druck.

**Verkaufsargument gegen PLAUD/Otter/Fireflies:** Wir verzichten auf US-Cloud-AI. Alles lokal.

---

## Plattform-Kontext: Olares OS

Das ist die wichtigste Architekturentscheidung des Projekts. Olares OS ist kein "normales Linux", sondern ein **Kubernetes-basiertes Betriebssystem** mit strengen Constraints. Jede Code-Entscheidung muss sich daran ausrichten.

**Olares stellt bereit (wir bauen das NICHT selbst):**
- Authentifizierung & Autorisierung (Authelia + Envoy Sidecar)
- PostgreSQL 16 als geteilte System-Middleware
- KVRocks (Redis-kompatibel, disk-persistent) als geteilte Cache/Queue
- MinIO + JuiceFS für Object Storage
- NATS für Messaging
- TLS-Provisioning (Cloudflare Tunnel / Tailscale)
- Reverse Proxy & Routing
- Backup-Infrastruktur

**Insilo besteht aus:**
- Frontend (Next.js 15 PWA)
- Backend (FastAPI)
- Whisper-Service (faster-whisper auf GPU)
- BGE-M3 Embedding-Service
- Celery-Worker für Background-Jobs

Alle laufen als separate Deployments im Namespace `insilo-<username>`, kommunizieren per Kubernetes-DNS.

**Kein eigenes LLM.** Insilo bringt seit dem LiteLLM-Umstieg keinen
Ollama-Container mehr mit — das spart ein 4-GB-Image und einen GPU-Slot.
Das Sprachmodell spricht Insilo als OpenAI-kompatiblen Endpunkt an;
üblicherweise die LiteLLM-App auf derselben Box. **Es gibt bewusst keinen
Vorgabewert** für die Adresse (siehe `docs/HANDOFF.md`, Abschnitt
„Gelöst in v0.1.72"): der Nutzer trägt sie unter `/einstellungen` ein.

---

## Olares-Constraints (für jede Code-Entscheidung)

Aus dem offiziellen Olares Deployment Guide:

1. **Keine eigene Authentifizierung implementieren.** Der Envoy-Sidecar vor jedem Pod validiert Tokens. Eingehende Requests an unsere Container sind bereits authentifiziert — trust them.

2. **Keine `hostNetwork`, kein `NodePort`, kein `LoadBalancer`.** Nur `ClusterIP`-Services. Externe Erreichbarkeit ausschließlich über deklarierte `entrances`.

3. **Keine ClusterRole-Bindings.** Wir sind streng auf den eigenen Namespace beschränkt.

4. **Keine Cross-Namespace-Direktcalls.** Wenn später eine andere App auf unsere Daten zugreifen will: Service Provider Pattern.

5. **Storage nur in drei Pfaden:**
   - `/app/data/` — persistent, überlebt Uninstall
   - `/app/cache/` — ephemer
   - `/app/Home/` — User-Files

6. **Image-Naming-Regel:** Olares-App-Name muss `^[a-z0-9]{1,30}$` matchen. **Folder-Name, `metadata.name`, `metadata.appid`, `Chart.yaml.name` müssen identisch sein.** Linter rejected sonst.

7. **Deployment-Template-Regel:** `metadata.name` muss der *literale* App-Name sein. `{{ .Release.Name }}` ist nicht erlaubt.

8. **Datenbank-Connection-Vars werden injiziert.** Wir bekommen `.Values.postgres.host`, `.Values.postgres.password` etc. zur Laufzeit. **Nicht hardcoden.**

9. **Ein Upgrade friert die Werte ein.** Olares spielt beim Aktualisieren
   die bei der *Installation* gespeicherten Werte wieder ein und übernimmt
   die Vorgaben des neuen Charts **nicht**. Was in `values.yaml` steht,
   bleibt damit auf dem Stand der ersten Installation stehen — dauerhaft.
   Deshalb darf nichts, das sich pro Version ändert, dort seine einzige
   Quelle haben. Der Image-Tag hängt seit v0.1.81 an `.Chart.AppVersion`
   (Metadaten kommen frisch an), nicht an `.Values.images.*.tag`.
   Hintergrund und Beweis: `docs/HANDOFF.md`, Abschnitt „Ein Markt-Upgrade
   tauscht die Images nicht aus".

10. **Eine Deinstallation löscht die Datenbank.** `/app/data` überlebt
    (das ist `permission.appData`), die Datenbank nicht — Olares legt sie
    neu an, samt neuer Org-Kennung. Weil Audio unter `audio/<org-id>/`
    liegt, hängen die vorhandenen Aufnahmen danach in der Luft. Dagegen
    schreibt `backend/app/konfiguration.py` einen Abzug der Einrichtung
    neben das Audio und liest ihn beim Start zurück, **wenn die Datenbank
    leer ist** — mit derselben Org-Kennung. Der Abzug **enthält
    Zugangsdaten** und liegt mit Rechten 0600.

---

## Tech-Stack

### Frontend (PWA)
- **Framework:** Next.js 15 (App Router, RSC)
- **Sprache:** TypeScript (strict mode)
- **Styling:** Tailwind CSS v4 + shadcn/ui
- **Icons:** das eine Set des AImighty-CI (`marke/icons/ui/`), Kopie unter `frontend/ci/`, gezeichnet über HB-SYMBOL (`components/symbol.tsx`, erzeugt nach `lib/symbole.tsx`) — kein `lucide-react`. Größen 16/20/24/40, Strich 1,5 px; Ausnahme nur der runde Aufnahmeknopf
- **State:** Zustand (lokal) + TanStack Query (Server-State)
- **Audio:** MediaRecorder API + WebRTC für Live-Streaming
- **Offline:** Service Worker mit Workbox, IndexedDB
- **PWA-Manifest:** standard

**Auth:** Wir nutzen **NICHT** Supabase Auth, NextAuth oder Ähnliches. Der Envoy-Sidecar von Olares prüft Authelia-Tokens, bevor Requests zu uns kommen. Die Benutzer-Identität bekommen wir aus dem Header `X-Bfl-User` (oder via Olares-API).

### Backend (FastAPI)
- **API:** FastAPI 0.115+
- **Sprache:** Python 3.11+
- **Datenbank-Client:** asyncpg + SQLAlchemy 2.x (kein Supabase-Client mehr)
- **Background-Jobs:** Celery mit KVRocks als Broker
- **Audio-Verarbeitung:** Aufruf an internen Whisper-Service
- **LLM-Calls:** OpenAI-kompatibler Endpunkt, Adresse pro Org aus `org_settings`
- **Embeddings:** Aufruf an internen BGE-M3-Service

### KI-Services (jeweils eigener Container)
- **Whisper:** `faster-whisper` mit `large-v3` Modell
- **Speaker Diarization:** pyannote.audio (über WhisperX)
- **LLM:** kein eigener Container — externer OpenAI-kompatibler Endpunkt
  (auf der Box: LiteLLM), Modellname frei konfigurierbar
- **Embeddings:** BGE-M3 (multilingual, Apache 2.0)

### Datenbank-Strategie
**Olares-System-PostgreSQL nutzen, kein Supabase.** Begründung: weniger Container, native Integration, Olares verwaltet Backups/Updates. Connection-Variablen werden via Helm-Values injiziert.

Wir nutzen folgende Extensions (deklariert im OlaresManifest):
- `vector` — für pgvector (Embeddings)
- `pg_trgm` — für Trigram-Suche
- `pgcrypto` — für verschlüsselte Felder

### Cache & Queue
- **KVRocks** statt Redis. Redis-API-kompatibel, also Celery + python-redis-lib funktionieren weiterhin. Hauptvorteil: disk-persistent.

### Realtime an die PWA
Drei Optionen, MVP-Empfehlung: **WebSocket vom FastAPI-Backend** an die PWA, intern PostgreSQL LISTEN/NOTIFY für DB-Events. Optional später: NATS-Anbindung.

---

## Multi-Box-Architektur

Trotz der Olares-Integration bleibt die PWA **box-agnostisch**: sie wird einmal gebaut, kann sich aber mit verschiedenen Olares-Boxen verbinden (für Berater, die mehrere Kunden betreuen).

Bei Olares ergibt sich die Box-URL automatisch aus dem Entrance:
```
https://insilo<routeID>.<username>.olares.com
```

Der Nutzer "hängt sich" über diese URL in die Box ein. Multi-Box-Support in der PWA: jede Box-URL bekommt ein eigenes IndexedDB-Profil (Slack-Workspace-Pattern).

---

## Verzeichnisstruktur

```
insilo/
├── CLAUDE.md                    # dieses Dokument
├── README.md
├── QUICKSTART.md
├── .env.example
├── .gitignore
├── docker-compose.yml           # nur für lokale Dev-Umgebung
│
├── docs/
│   ├── ARCHITECTURE.md          # System-Architektur, Datenfluss
│   ├── DESIGN.md                # Design-System (AImighty-Token)
│   ├── ROADMAP.md               # Phasen 1-6
│   ├── SECURITY.md              # Sicherheit (Olares macht das meiste)
│   ├── DEPLOYMENT.md            # Olares-Paketierung, GHCR, Markt-Upload
│   └── PLATFORM.md              # Langfristige Multi-App-Vision
│
├── frontend/                    # Next.js 15 PWA
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── next.config.mjs
│   ├── Dockerfile
│   └── public/manifest.json
│
├── backend/                     # FastAPI
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── app/main.py
│
├── supabase/                    # NUR für lokale Entwicklung
│   ├── migrations/
│   │   ├── 0001_initial_schema.sql
│   │   └── 0002_extensions.sql
│   └── seed.sql
│
└── olares/                      # Helm-Chart für Olares-Markt
    ├── Chart.yaml
    ├── OlaresManifest.yaml
    ├── values.yaml
    ├── templates/
    │   ├── deployment-frontend.yaml
    │   ├── deployment-backend.yaml
    │   ├── deployment-whisper.yaml
    │   ├── deployment-embeddings.yaml
    │   ├── deployment-worker.yaml
    │   ├── services.yaml            # alle ClusterIP-Services
    │   └── configmap-migrations.yaml
    └── README.md
```

---

## Designsystem (Kurzfassung — Vollversion in `docs/DESIGN.md`)

**Insilo läuft seit 18. August 2026 auf dem AImighty-Designsystem.**
Das frühere eigene System (Weiß/Schwarz/Gold, Lexend Deca + Inter, Anker
HubSpot/aimighty/PLAUD) ist abgelöst.

**Werte, Zeichen und Bausteine kommen aus dem CI; Abweichung nur über
`ABGLEICH.md`.** Quelle ist das Repo `ska1walker/aimighty-ci` (CI
`STAND.md`, Kai 1.10.2026). Insilo hält einen Stand `ci-YY.M.n` als Kopie
unter `frontend/ci/` (mit `stand.json`), geholt mit
`node scripts/ci-holen.mjs --von <klon> --stand ci-YY.M.n` aus `frontend/` —
**nie `main`, nie zur Bauzeit**. Danach:

- Der Token-Block oben in `frontend/app/globals.css` ist wörtlich
  `ci/tokens/app.css`.
- Jeder `AM-`/`HB-` Abschnitt in `globals.css` ist wörtlich
  `ci/bauteile/<KENNUNG>.css`; Insilos Eigenes steht unter `IN-`
  (`docs/DESIGN.md` §4a).
- Jedes Zeichen kommt aus `ci/marke/icons/ui/` über HB-SYMBOL
  (`components/symbol.tsx`, erzeugt nach `lib/symbole.tsx`) — kein
  `lucide-react`, Größen 16/20/24/40, Strich 1,5 px; Ausnahme nur der
  runde Aufnahmeknopf.

**Ändern nur im CI**: dort PR, mergen, die Action setzt einen neuen Stand
und öffnet hier von selbst einen PR „CI-Stand ci-…“ (seit `ci-26.10.12`,
CI `STAND.md` „Nachziehen“); bei grün mergen. Wer in Insilo ausprobiert, sieht die eigene CI rot werden —
das ist gewollt. Eine Abweichung, die bleiben soll, steht als Eintrag mit
Kais Entscheidung im Abschnitt „Insilo“ der CI-`ABGLEICH.md`, nie still
hier. Was wacht: `tests/ci-stand.test.ts` (Kopie, Token-Block, Bausteine),
`tests/abschnitte.test.ts` (jede Kopfzeile mit Kennung),
`tests/symbole.test.ts` (Zeichen), `tests/kontrast.test.ts`,
`tests/wording.test.ts` (AI, in allen Sprachen), `tests/sprachen.test.ts`.

`frontend/tailwind.insilo.preset.js` ist eine unveränderte Kopie aus der
Lieferung und liest die Token über `var(--am-*)`.

**Farbe:** Hanseatenblau trägt die Fläche, Gold zeichnet aus. Im
Dunkelmodus handelt Gold — Blau auf Blau trägt nicht.

**Typografie:** Geist Sans + Geist Mono, selbst gehostet aus
`frontend/app/fonts/`. Kein Google-CDN, auch nicht zur Bauzeit.

**Raum:** Grundeinheit 4 px × Dichte (weit 1,1 · normal 1,0 · kompakt
0,9). Zielgrößen 40 px Zeiger / 44 px Berührung, ohne Ausnahme.

**Hülle:** drei Bereiche — Navigation, Inhalt, Ablage. Die Ablage trägt
Kontext zum gewählten Ding und ist nie eine zweite Inhaltsspalte.

**Zustände:** Farbe trägt eine Aussage nie allein — immer Zeichen und
Satz dazu.

**Identitäts-Signatur:** Gold zeichnet die laufende Aufnahme aus (Punkt,
Knopf, pulsierende Linie). Rot bleibt dem Fehler vorbehalten.

**Datenschutz-Nachweis:** unten in der Navigation, **nur mit gemessenen
Werten — sonst gar nicht**. Details in `docs/DESIGN.md §5`. Diese Regel
ist keine Formalie: Insilo ist nicht pauschal „0 Byte", sobald ein
externer LLM-Endpunkt oder ein Webhook konfiguriert ist.

**Anti-Patterns:** keine Gradients, kein Glassmorphism, keine
Parallaxe, keine scroll-getriggerten Effekte, keine AI-Sparkles, keine
hüpfenden Knöpfe.

---

## Sprache & Schreibstil

- **UI:** vollständig internationalisiert (DE/EN/FR/ES/IT), Default DE.
  Texte liegen in `frontend/messages/{de,en,fr,es,it}.json`, abgerufen via
  `useTranslations()` (next-intl). Sprachen-Resolution: User-Override (DB) >
  Org-Default (DB) > Browser Accept-Language > 'de'.
- **Anrede pro Sprache:** DE → Sie-Form; EN → "you"; FR → "vous";
  ES → "usted"; IT → "Lei" / formelle Anrede.
- **Microcopy:** sachlich, präzise, ohne Marketing-Sprech — sprachübergreifend.
- **Fehlermeldungen:** menschlich, lösungsorientiert, in allen 5 Sprachen.
- **Code-Kommentare und commit messages:** weiter Englisch.
- **Docs (HANDOFF, README, ARCHITECTURE, CLAUDE.md):** weiter Deutsch
  — internes Maintainer-Material.

---

## Kernprinzipien

1. **Datensouveränität ist nicht verhandelbar.** Keine Telemetrie. Kein Phone Home. Externe Schriften in Production self-hosten.

2. **Olares-native.** Nutze Plattform-Services (PostgreSQL, KVRocks, MinIO, Auth) statt eigene zu bauen.

3. **Multi-Tenant von Anfang an.** Mehrere User pro Olares-Box möglich. Row-Level Security in PostgreSQL.

4. **Offline-First wo möglich.** PWA muss Meetings im Cache anzeigen, auch wenn Box gerade nicht erreichbar.

5. **Audit-Trail.** Jede Datenänderung wird geloggt.

6. **Reversibilität.** Soft-Delete + 30-Tage-Frist vor Hard-Delete.

7. **Performance ist UX.** Background-Jobs + Progress-Indicators.

8. **Keep it boring.** Erprobte Pfade, keine bleeding-edge-Experimente.

---

## Phasenplan (Detail in `docs/ROADMAP.md`)

- **Phase 1 (jetzt):** Setup, Schema, Box-Onboarding, Aufnahme + Whisper-Transkription
- **Phase 2:** LLM-Zusammenfassungen, Speaker Diarization, Template-System
- **Phase 3:** "Ask"-Funktion (RAG), Live-Transkription
- **Phase 4:** Olares-App-Paketierung, Markt-Upload
- **Phase 5:** Pilot-Deployment, erste Kunden
- **Phase 6:** Skalierung, Plattform-Erweiterung

---

## Wie Claude Code in diesem Repo arbeitet

1. **Vor jeder Code-Entscheidung:** `docs/ARCHITECTURE.md` und Olares-Constraints aus dieser CLAUDE.md lesen. Bei Olares-Themen zusätzlich `docs/HANDOFF.md §7g` — codifiziert die teuren Lessons aus v0.1.7→v0.1.17.
2. **Bei UI-Arbeit:** Werte, Zeichen und Bausteine kommen aus dem AImighty-CI (`ska1walker/aimighty-ci`, Kopie unter `frontend/ci/`); Abweichung nur über `ABGLEICH.md` dort (Abschnitt „Designsystem“ oben). Die Regeln stehen im CI (`kern/`, `medien/app.md`, `bauteile/`), Insilos Ergänzungen in `docs/DESIGN.md`. Generische Design-Skills sind nachrangig.
3. **Bei Backend-Änderungen:** Wir bauen *keine* Auth-Logik. Eingehende Requests sind authentifiziert via Envoy. User-ID kommt aus `X-Bfl-User` Header.
4. **Bei DB-Schema-Änderungen:** Migration in `supabase/migrations/0NNN_*.sql` anlegen, RLS auf jede neue Tabelle, **dann `python3 scripts/regen-migrations.py` laufen lassen** — das mirroret die SQL in `olares/files/` und regeneriert die inlinete `olares/templates/configmap-migrations.yaml`. CI bricht sonst beim Drift-Check ab.
5. **Bei Storage:** Nur `/app/data/`, `/app/cache/`, `/app/Home/`. Niemals beliebige Pfade.
6. **Bei Olares-Manifest- oder Chart-Änderungen:** **Vor dem Commit `bash scripts/check-chart.sh` laufen lassen.** Das Script codiert die Phase-4-Learnings — Version-Sync (Marc's Golden Rule), keine `.Files.Get`, keine Helm-Hooks (chicken-and-egg `ns-owner`-Label), kein `runAsInternal: true`, SQL-Drift, helm lint + template. Vollständiges Detail in `docs/HANDOFF.md §7g`. Selbe Checks laufen in CI (`ci.yml.chart-checks`) und blockieren Image-Builds (`release.yml.preflight`).
7. **Bei neuem Git-Tag `v*.*.*`:** Tag-Name muss `olares/Chart.yaml.version` matchen — `release.yml` bricht sonst ab. Am einfachsten via `scripts/release.sh X.Y.Z` — bumpt alle 4 Versionsstellen, regen-Migrationen, check-chart, helm package, commit, tag, push, copy to `~/Downloads/`. **Image-Tags werden nicht mehr gebumpt:** sie hängen seit v0.1.81 an `Chart.AppVersion` (siehe Constraint 9), `values.yaml` trägt `tag: ""`. Flag `--chart-only` schreibt dort ausnahmsweise einen Pin auf die Vorversion — das Chart zieht dann weiter die bewährten Images und der Image-Build entfällt. `--dry-run` zeigt was passieren würde. `--no-push` stoppt lokal nach Tag.

   **Wichtig zum Zusammenspiel mit `release.yml`:** der Workflow leitet die Image-Version aus dem **Git-Tag** ab, nicht aus `values.yaml`. Bis v0.1.61 lief der Build bei `--chart-only` deshalb trotzdem durch und erzeugte Images, die niemand referenziert (die frühere Behauptung „spart GH-Actions-Build" war schlicht falsch). Seit v0.1.61 überspringt `release.yml` den Build, wenn `values.yaml` den gepushten Tag nicht referenziert. Falls das mal fälschlich greift: `release`-Workflow manuell via `workflow_dispatch` mit expliziter Version starten.
   **Seit 0.1.103 (wie Rocket):** Ein Merge nach `main` mit neuer Version
   in `olares/Chart.yaml` baut die Images und legt Tag und Release selbst
   an; danach bringt `markt.yml` die Version in den Markt. Der Tag von Hand
   ist nicht mehr nötig. Je Version gehört `olares/markt/<version>.md` dazu
   (Skill `olares-release`, §6a).
   **Kennung des Markts (6.10.2026):** Kais Box kennt den AImighty-Markt als
   `market.aimighty` (klein; Groß- und Kleinschreibung zählen). Meldet sich
   der Markt anders (`SOURCE_ID` in Marcs `functions/_lib.ts`), übernimmt die
   Box kein Update, obwohl die neue Version im Markt steht. Gehalten wird die
   Kennung von Rockets Action `markt.yml` (`MARKT_QUELLE`); ein „Run
   workflow“ dort mit Rockets aktueller Version richtet sie. Insilo steht im
   Markt unter „AI“. Einzelheiten: Rocket `docs/MARKT.md`, „Kennung des Markts“.
8. **Bei Veröffentlichung in einen Store:** Skill `olares-release`
   (`.claude/skills/olares-release/SKILL.md`) — Pfadwahl, Reihenfolge
   (erst ausrollen, dann hochladen) und die offenen Punkte für den
   öffentlichen Markt. Olares' eigene CLI bringt dazu vierzehn gepflegte
   Skills mit (`npx @olares/cli@latest install`); die gehen bei
   Plattformfragen vor.
9. **Sprachregel:** UI-Texte über `useTranslations()` aus `frontend/messages/*.json` (5 Sprachen). Default DE / Sie-Form, formelle Anrede in allen Sprachen. Code + Commit-Messages weiter Englisch. Neue inline-Strings → erst Key in alle 5 JSONs aufnehmen, dann `t('namespace.key')` verwenden.
10. **Tests:** Vitest fürs Frontend, pytest fürs Backend. Kritische Pfade (Audio-Upload, Transkription) immer mit Tests.

    **Rundgang im Browser** (`frontend/e2e/`, nach Rocket): jede Seite auf
    Desktop und Handy, hell und dunkel — API-Fehler, Skriptfehler,
    Überlauf und Abgeschnittenes, genau eine h1, Symbolknöpfe mit Namen und
    Tooltip, Zeichengrößen, axe einschließlich Kontrast. Läuft in der CI
    als Job `oberflaeche` gegen echte Datenbank mit `e2e/beispiel/`.
    Lokal: App starten, dann `INSILO_URL=… npm run e2e` (in einer
    Claude-Sitzung mit `INSILO_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`).
    Eine neue Seite kommt in `SEITEN` in `e2e/rundgang.spec.ts`.
11. **Bei Unsicherheit:** stoppen und Kai fragen.
12. **Sitzungen** (Kai, 5.10.2026): Eine Sitzung je App und je größerem
    Thema, nicht eine endlose — das Gedächtnis sind diese Datei und `docs/`.
    Eine Insilo-Sitzung hat `ska1walker/insilo` und `ska1walker/aimighty-ci`
    mit Schreibrecht, dazu `ska1walker/aimighty-market` zum Prüfen des Markts.
    Eine gemeinsame Änderung (Token, Zeichen, `AM-`/`HB-`) beginnt in der
    App-Sitzung, die sie braucht: dort ausprobieren, PR ins CI, mergen; die
    Action `stand` öffnet dann in jeder App einen PR „CI-Stand ci-…“. Diese
    PRs mergt dieselbe Sitzung bei grün, auch in Rocket — wenn Rocket mit
    Schreibrecht verbunden ist. **Zu Beginn jeder Sitzung** nach offenen PRs
    „CI-Stand ci-…“ in diesem Repo sehen und sie bei grün mergen (rot: im
    selben PR anpassen). Eine eigene CI-Sitzung nur für reine
    Designsystem-Arbeit (Abgleich-Pakete, Regeln, eine neue App anschließen),
    mit allen Apps verbunden. Nie zwei Sitzungen auf demselben Zweig; im
    CI-Repo nur ein offener PR zur Zeit, weil jeder Merge einen Stand setzt
    (CI `STAND.md`, „Sitzungen“).

---

## Was NICHT gebaut wird

- ❌ Eigene Authentifizierung (Olares macht das)
- ❌ Eigenes Supabase-Stack (PostgreSQL kommt von Olares)
- ❌ Mobile Native Apps (PWA reicht)
- ❌ Cloud-Sync zwischen Boxen (würde Kernversprechen brechen)
- ❌ Externe AI-API-Fallbacks
- ❌ Telemetrie & Tracking
- ❌ Marketplace für Templates (Phase 5+)

---

## Kontakt / Ownership

- **Product & Code:** Kai Böhm (kaivo.studio)
- **Vertrieb:** aimighty.de
- **Hosting:** Kundenseitig (Olares-Box)
- **Eigene Infrastruktur:** Vercel + Supabase EU (nur für kaivo.studio Marketing/CRM, NICHT Kundendaten)
