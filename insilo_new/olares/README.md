# Olares-Paketierung

Dieses Verzeichnis enthält das vollständige Helm-Chart für Insilo. Es entspricht der Olares-Spezifikation v0.11.0.

---

## Verzeichnisstruktur

```
olares/
├── Chart.yaml                              # Helm-Metadaten
├── OlaresManifest.yaml                     # Olares-spezifische Konfiguration
├── values.yaml                             # Default-Werte
├── README.md                               # diese Datei
└── templates/
    ├── deployment-frontend.yaml            # Next.js PWA
    ├── deployment-backend.yaml             # FastAPI
    ├── deployment-worker.yaml              # Celery-Worker
    ├── deployment-whisper.yaml             # Whisper (GPU)
    ├── deployment-ollama.yaml              # Qwen 2.5 (GPU)
    ├── deployment-embeddings.yaml          # BGE-M3
    └── services.yaml                       # alle ClusterIP-Services
```

---

## Vor dem ersten Upload

### 1. Container-Images bauen und nach GHCR pushen

Vier Images werden gebraucht (das fünfte, `ollama/ollama`, kommt direkt von Ollama):

```bash
# Frontend
cd ../frontend
docker build -t ghcr.io/ska1walker/insilo-frontend:0.1.0 .
docker push ghcr.io/ska1walker/insilo-frontend:0.1.0

# Backend (gleiches Image für Worker)
cd ../backend
docker build -t ghcr.io/ska1walker/insilo-backend:0.1.0 .
docker push ghcr.io/ska1walker/insilo-backend:0.1.0

# Whisper Service
cd services/whisper
docker build -t ghcr.io/ska1walker/insilo-whisper:0.1.0 .
docker push ghcr.io/ska1walker/insilo-whisper:0.1.0

# Embeddings Service
cd ../embeddings
docker build -t ghcr.io/ska1walker/insilo-embeddings:0.1.0 .
docker push ghcr.io/ska1walker/insilo-embeddings:0.1.0
```

**Wichtig:** Alle GHCR-Pakete auf **Public** stellen, sonst kann Olares sie nicht ziehen.

### 2. Paket bauen

Aus dem Projekt-Root:

```bash
cd olares/..   # eine Ebene über olares/
mv olares insilo   # Olares verlangt: Folder-Name = App-Name
tar -czf insilo-0.1.0.tgz insilo/
```

**Linter-Regel:** Der Folder muss exakt `insilo` heißen (matching `metadata.name`, `metadata.appid`, `Chart.yaml.name`). Wenn das Verzeichnis `olares/` heißt, muss es vor dem Verpacken umbenannt werden.

### 3. Upload nach Olares

#### Variante A: Studio (für Tests)

1. Olares aufrufen, **Studio** öffnen
2. **Create a new application** → Name `insilo`
3. Drag-and-drop oder Upload das `.tgz`-Paket

#### Variante B: Markt (für produktive Installation)

1. **Market** → **My Olares** → **Upload custom chart**
2. `.tgz` auswählen
3. Wartung der Upload-Validierung (Linter läuft serverseitig)
4. **Install now** klicken

---

## Aktualisierungen

Bei jedem Versionssprung:

1. `Chart.yaml.version` erhöhen (Semver-Regel)
2. `Chart.yaml.appVersion` an `spec.versionName` in `OlaresManifest.yaml` anpassen
3. `metadata.version` in `OlaresManifest.yaml` muss `Chart.yaml.version` matchen
4. `spec.upgradeDescription` aktualisieren
5. Container-Images mit neuem Tag bauen und pushen
6. `values.yaml` Image-Tags anpassen
7. Neues `.tgz` bauen und hochladen

---

## Linter-Fehler und Lösungen

Aus dem offiziellen Olares-Deployment-Guide, die häufigsten Fallen:

| Linter-Fehler                                         | Ursache                                                                   | Fix                                                  |
|-------------------------------------------------------|---------------------------------------------------------------------------|------------------------------------------------------|
| `invalid folder name`                                 | Folder enthält Bindestrich oder Großbuchstaben                            | Folder-Name = `insilo` (no hyphens)                  |
| `appid is required`                                   | `appid` fehlt in `metadata`                                               | `appid: insilo` ergänzen                             |
| `requiredDisk must satisfy regexp`                    | `requiredDisk` fehlt oder falsches Format                                 | `requiredDisk: 60Gi` setzen                          |
| `deployment name must equal app name`                 | `metadata.name` nutzt `{{ .Release.Name }}`                               | Literal `insilo-frontend` etc. eintragen             |
| `name mismatch`                                       | Folder, `metadata.name`, `appid`, `Chart.yaml.name` unterschiedlich       | Alle 4 müssen identisch sein                         |
| `service type not allowed`                            | NodePort oder LoadBalancer verwendet                                      | `type: ClusterIP` setzen                             |

---

## Lokales Testen vor Upload

In Studio die *Preview*-Funktion nutzen — das prüft die Manifest-Validierung ohne tatsächliche Installation.

Bei `app fails to start`: Logs in Studio einsehen (Bottom Bar). Häufigste Ursachen:
- Container-Image nicht öffentlich verfügbar
- Port-Mismatch zwischen Dockerfile `EXPOSE` und Manifest `containerPort`
- Fehlender Middleware-Vars (Postgres/Redis im Manifest deklarieren!)

---

## Migration-Pfad (falls Olares-Lock-in vermieden werden soll)

Das aktuelle Chart ist so geschrieben, dass es theoretisch auch auf normalem Kubernetes laufen könnte, wenn:
1. `.Values.postgres.*`, `.Values.redis.*` durch eigene Werte ersetzt werden
2. Authelia-Schutz durch eigene Auth ersetzt wird
3. Storage-Pfade auf normale PersistentVolumes umgestellt werden

Das gibt Insilo grundsätzliche Portabilität, falls die Olares-Plattform in Zukunft anders ausgerichtet werden müsste.
