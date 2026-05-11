# Olares Deployment

Dieses Verzeichnis enthält das Olares-App-Manifest, mit dem das Produkt als ein-Klick-installierbare App auf einer Olares-Box landet.

## Erstmaliges Paketieren

1. Olares Studio installieren ([Anleitung](https://docs.olares.com/developer/develop/))
2. In diesem Verzeichnis: `olares-cli package`
3. Resultierendes `.olares`-Paket in privates Repository hochladen

## Container Images

Vor dem Paketieren müssen alle Container-Images verfügbar sein:

```bash
# Frontend
docker build -t ghcr.io/kaivo-studio/insilo-frontend:0.1.0 ../frontend
docker push ghcr.io/kaivo-studio/insilo-frontend:0.1.0

# Backend (auch für Worker)
docker build -t ghcr.io/kaivo-studio/insilo-backend:0.1.0 ../backend
docker push ghcr.io/kaivo-studio/insilo-backend:0.1.0

# Whisper Service
docker build -t ghcr.io/kaivo-studio/insilo-whisper:0.1.0 ../backend/services/whisper
docker push ghcr.io/kaivo-studio/insilo-whisper:0.1.0

# Embeddings Service
docker build -t ghcr.io/kaivo-studio/insilo-embeddings:0.1.0 ../backend/services/embeddings
docker push ghcr.io/kaivo-studio/insilo-embeddings:0.1.0
```

## Modelle vorladen

Damit die App auf der Kundenbox sofort funktioniert, müssen die Modelle vor der Auslieferung im Werkstatt-Modus geladen werden — siehe `docs/DEPLOYMENT.md` Abschnitt 4.

## Testen auf eigener Olares-Instanz

```bash
# Auf eigener Olares-Box anmelden via LarePass
# Dann die Paket-Datei hochladen oder per CLI:
olares-cli install ./insilo-0.1.0.olares
```

Mehr Details: `docs/DEPLOYMENT.md`.
