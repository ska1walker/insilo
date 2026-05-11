# Deployment

> Wie das Produkt auf eine Olares-Box kommt und wie es dort aktualisiert wird.

---

## 1. Deployment-Modi

### Modus A — Vorkonfigurierte Box (Standard)

kaivo.studio liefert eine **vorkonfigurierte Olares One** beim Kunden aus.

**Vorbereitung im Werkstatt-Modus:**
1. Olares One ausgepackt, mit Netzteil verbunden
2. Olares OS auf neueste stabile Version updaten
3. insilo-App-Paket installieren (über privates Olares-Repository)
4. Initial-Migration: Default-Org, erster Admin-User
5. Modelle vorladen: Whisper large-v3, Qwen 2.5 14B Q4, BGE-M3
6. Health-Check ausführen
7. Box wird in spezielle Versand-Verpackung verpackt

**Vor-Ort beim Kunden:**
1. Box ans Stromnetz und Netzwerk anschließen
2. Per QR-Code in der Admin-UI: Box im lokalen DNS registrieren (z.B. `meeting.kanzlei-mueller.de`)
3. TLS-Zertifikat wird automatisch ausgestellt (via Let's Encrypt oder eigener interner CA)
4. Admin loggt sich erstmals ein, Passwort ändern
5. Weitere User anlegen
6. Schulung (2-3 Stunden vor Ort)

### Modus B — Bring-Your-Own-Box

Kunde hat bereits eine Olares-fähige Hardware. insilo-App-Paket wird über das private Repository installiert.

### Modus C — Cloud-Variante (NICHT angeboten)

Wird bewusst nicht angeboten — wäre Vertragsbruch mit dem Kernversprechen.

---

## 2. Olares-App-Manifest

Die App wird gemäß Olares-App-Spezifikation paketiert. Vereinfachtes Manifest:

```yaml
# olares/OlaresManifest.yaml
apiVersion: app.bytetrade.io/v1alpha1
metadata:
  name: insilo
  title: insilo
  version: 0.1.0
  description: "On-Premise Meeting-Intelligenz"
  publisher: kaivo.studio
  categories:
    - Productivity
    - AI
spec:
  versionName: "0.1.0"
  fullDescription: |
    Datensouveräne Meeting-Aufnahme, Transkription und Analyse —
    vollständig auf der eigenen Hardware.

  requiredMemory: 64Gi
  requiredCPU: 8
  requiredDisk: 200Gi
  requiredGPU:
    nvidia.com/gpu: 1

  options:
    appScope:
      clusterScoped: false
      appRef: []

  middleware:
    postgres:
      username: insilo_admin
      databases:
        - name: insilo
          extensions:
            - vector
            - pg_trgm
            - uuid-ossp
    redis:
      namespace: insilo

  permission:
    appData: true
    sysData: false

entrances:
  - name: insilo-app
    host: insilo
    port: 3000
    title: "insilo"
    icon: /icons/app-icon.png
    authLevel: private
```

---

## 3. Container-Topologie

```
┌─────────────────────────────────────────────────────────────┐
│                    insilo-namespace                         │
│                                                             │
│  Frontend (Next.js)        ──→  Port 3000  → Olares Ingress │
│  Backend (FastAPI)         ──→  Port 8000  → Internal       │
│  Celery Worker (×2)        ──→  No port (background)        │
│  Whisper Service (FastAPI) ──→  Port 8001  → Internal, GPU  │
│  Ollama                    ──→  Port 11434 → Internal, GPU  │
│  BGE Embedding Service     ──→  Port 8002  → Internal       │
│                                                             │
│  Supabase Stack:                                            │
│  ├─ PostgreSQL 16          (Olares-managed Middleware)      │
│  ├─ GoTrue (Auth)          ──→  Port 9999                   │
│  ├─ Realtime               ──→  Port 4000                   │
│  ├─ Storage                ──→  Port 5000                   │
│  └─ PostgREST              ──→  Port 3001                   │
│                                                             │
│  Redis                     (Olares-managed Middleware)      │
│                                                             │
│  Persistence-Volumes:                                       │
│  ├─ /data/audio            (Audio-Originale)                │
│  ├─ /data/models           (Whisper, Qwen, BGE)             │
│  └─ /data/uploads          (Temp-Uploads)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Erstinstallation & Model-Download

Beim ersten Start der App müssen die KI-Modelle heruntergeladen werden. Das passiert im Werkstatt-Modus mit Internet-Verbindung, **nicht** beim Kunden.

```bash
# Whisper
huggingface-cli download Systran/faster-whisper-large-v3 \
  --local-dir /data/models/whisper-large-v3

# Qwen 2.5 14B
ollama pull qwen2.5:14b-instruct-q4_K_M

# BGE-M3
huggingface-cli download BAAI/bge-m3 \
  --local-dir /data/models/bge-m3
```

**Wichtig:** Nach Modell-Download wird die Box bewusst vom Internet getrennt, bevor sie zum Kunden ausgeliefert wird (außer Kunde wählt Auto-Update-Modus).

---

## 5. Update-Mechanismus

### Modus 1: Auto-Pull (Default)

```
┌────────────┐    täglich, 03:00 Uhr   ┌──────────────────────┐
│  Olares-   │ ─────────────────────→ │ updates.kaivo.studio │
│  Box       │ ←───────────────────── │  (Vercel-Edge)        │
└────────────┘    Version-Manifest    └──────────────────────┘

Falls neue Version verfügbar:
1. Download des signierten Update-Pakets
2. Signatur-Validierung (Cosign + öffentlicher Key)
3. Stage: in /opt/insilo/staging
4. Nächstes Wartungsfenster (Kunde-konfigurierbar):
   - Active Connections wartens lassen
   - Migrations ausführen
   - Container neustarten (Rolling)
5. Health-Checks
6. Bei Erfolg: Promote staging → production
7. Bei Fehler: Rollback auf Vorgängerversion
```

**Was wird übertragen:** Container-Images + Migrations + Manifest. **Niemals** Kundendaten in Gegenrichtung.

### Modus 2: Manuelle Freigabe

Box meldet "Update verfügbar" in der Admin-UI. Admin entscheidet aktiv. Sonst identisch zu Modus 1.

### Modus 3: Air-Gapped

Keine Outbound-Verbindung. kaivo.studio sendet:
- Signiertes Update-Paket auf USB-Stick per Einschreiben
- Oder: über SFTP zu einer kunden-betriebenen DMZ-Maschine

Kunde-Admin importiert über die Admin-UI: "Update aus Datei einspielen".

---

## 6. Backup-Strategie

**Box-seitig (Kunde-Verantwortung):**
- Olares hat eingebautes Velero-Backup
- Empfohlene Frequenz: täglich inkrementell, wöchentlich voll
- Backup-Ziel: Kunde-eigener NAS oder verschlüsselter S3-Bucket
- **NIEMALS** automatisches Backup in kaivo.studio-Infrastruktur

**App-seitig:**
- DB-Dump-Funktion in der Admin-UI (manuell)
- Export von Meeting-Daten als ZIP (Audio + Transkript + Notiz)
- Vor jeder Major-Update wird automatisch ein Restore-Point erstellt

---

## 7. Remote-Support

**Aktivierungsflow (Kunde-Seite):**

1. Admin geht in Settings → Support
2. Klickt "Remote-Support aktivieren"
3. System generiert einmaligen Token, gültig für 24h
4. Tailscale-Verbindung zu kaivo.studio-Support-Server wird aufgebaut
5. Verbindung erscheint im Audit-Log
6. Nach Abschluss: Admin deaktiviert manuell (oder Auto-Ablauf nach 24h)

**Während aktiv:**
- Support-Mitarbeiter sieht NUR Logs und kann Container-Commands ausführen
- KEIN direkter DB-Zugriff auf User-Daten
- Jede Aktion wird im Audit-Log dokumentiert

---

## 8. Monitoring & Health

**Auf der Box (lokal):**
- Olares-Dashboard zeigt: CPU, GPU, RAM, Disk, Network
- App-spezifische Health-Endpoints:
  - `/health/api` — Backend erreichbar
  - `/health/db` — PostgreSQL erreichbar
  - `/health/whisper` — Transkriptions-Service bereit
  - `/health/ollama` — LLM antwortet
  - `/health/embeddings` — Embedding-Service bereit

**An kaivo.studio:**
- **Standardmäßig: nichts.** Keine Telemetrie.
- **Optional (Kunde aktiviert):** Heartbeat-Ping zur kaivo.studio-Monitoring-API. Enthält NUR: Version, Uptime, Letzter Erfolgreicher Job. Keine Inhalte, keine User-Daten.

---

## 9. Disaster Recovery

**Szenarien & Reaktion:**

| Szenario                          | Reaktion                                      |
|-----------------------------------|-----------------------------------------------|
| Box-Hardware-Ausfall              | Replacement-Box vorkonfiguriert ausliefern, Backup einspielen |
| SSD-Defekt                        | Zweite SSD-Slot der Olares One als Fallback   |
| Falsche Update-Installation       | Auto-Rollback auf Vorgängerversion            |
| Kunde löscht versehentlich Daten  | Soft-Delete: 30 Tage Wiederherstellbar        |
| Ransomware-Verdacht               | Sofortiges Disconnect, Velero-Restore         |
| Naturkatastrophe                  | Off-Site-Backup-Restore auf neuer Box         |

**RPO (Recovery Point Objective):** 24 Stunden (täglich Backup)
**RTO (Recovery Time Objective):** 4 Stunden (Replacement-Box + Restore)

Diese SLAs sind Premium-Vertragsbestandteil, nicht Default.

---

## 10. Werkstatt-Checklist (vor Versand)

```
□ Olares OS aktuell
□ insilo-App in Production-Version installiert
□ Whisper-Modell geladen und getestet
□ Ollama-Modell geladen und getestet
□ BGE-Modell geladen und getestet
□ Datenbank-Migrations erfolgreich
□ Default-Admin angelegt (Passwort im versiegelten Briefumschlag)
□ Test-Aufnahme: durch alle Stufen erfolgreich
□ Health-Endpoints alle grün
□ TLS-Zertifikat-Provisioning getestet
□ Backup-Endpoint funktioniert
□ Audit-Log läuft
□ Auslieferungsdokumente (Übergabeprotokoll, Quick-Start) beiliegen
□ Verpackung mit Versiegelungsstickern
```
