# Deployment

> Wie Insilo auf eine Olares-Box kommt — drei Wege.

---

## 1. Deployment-Modi

### Modus A — Markt-Installation (Standard, Phase 5+)

Insilo ist im offiziellen Olares-Markt veröffentlicht. Der Kunde:

1. Öffnet Olares-Desktop
2. Geht zu **Market** → sucht "Insilo"
3. Klickt **Install**
4. Akzeptiert Permissions
5. Wartet auf Installation (~5-10 Min für Modell-Pulls)
6. App erscheint als Desktop-Icon

**Vorteile:**
- Update-Pfad via Markt eingebaut
- Vom Kunden selbst durchführbar
- Niedrige Vertriebskosten

**Voraussetzung:** Insilo muss im Markt veröffentlicht und freigegeben sein.

### Modus B — Custom Chart Upload (für Pilotphasen)

Solange Markt-Release noch nicht erfolgt ist, oder für Custom-Builds:

1. **Market** → **My Olares** → **Upload custom chart**
2. `.tgz`-Datei auswählen
3. Wartung des Linter-Checks
4. **Install now**

**Wann genutzt:** Pilotkunden vor Markt-Release, kundenspezifische Builds.

### Modus C — Studio-Test (Entwicklung)

Während der Entwicklung läuft Insilo in Olares Studio:

1. **Studio** → **Create a new application**
2. **Port your own container to Olares**
3. Image, Port, Env, Volumes konfigurieren
4. Click **Create**
5. Test mit **Preview**

**Apps haben `-dev`-Suffix.** Nur für Entwicklung/Tests, nicht für Produktivnutzung.

---

## 2. Werkstatt-Modus (Vorkonfiguration)

Bei Verkauf liefern wir **vorkonfigurierte** Olares-Boxen:

### Schritte beim Hersteller (kaivo.studio Werkstatt)

```bash
# 1. Olares-Box auspacken, Strom + Netz anschließen
# 2. Olares-OS auf aktuellen Stand updaten
sudo olares-cli upgrade

# 3. Insilo aus Markt installieren
# (via Olares-UI: Market → Insilo → Install)

# 4. KI-Modelle vorladen (sonst beim ersten Kundenstart langes Warten)
#    Diese Modelle landen in /app/cache des insilo-Namespaces
docker exec insilo-ollama ollama pull qwen2.5:14b-instruct-q4_K_M

# 5. Initial-Migration durchführen
#    (geschieht automatisch beim ersten App-Start)

# 6. Erstadmin-Account anlegen
#    Olares-Admin → Users → Create user

# 7. Health-Checks ausführen
curl https://<insilo-url>/health
```

### Beim Versand

- Box wird per Einschreiben oder Spedition geliefert
- Verschlusssiegel-Aufkleber zur Manipulationserkennung
- Versiegelter Briefumschlag mit Initial-Passwort
- Quick-Start-Karte mit URL und Login-Hinweisen

---

## 3. Vor-Ort-Installation beim Kunden

**Zeitbedarf:** 2-4 Stunden vor Ort.

```
1. Box ans Stromnetz + LAN anschließen
2. Box hochfahren lassen (ca. 5 Min)
3. Im lokalen DNS Eintrag setzen: insilo.kanzlei-mueller.de → Box-IP
4. (Optional) Cloudflare Tunnel konfigurieren für Außenzugriff
5. Admin-Login mit versiegeltem Passwort
6. Passwort ändern (Olares-Settings)
7. Weitere User in Olares anlegen
8. Insilo-App öffnen, durch Onboarding klicken
9. Erste Test-Aufnahme machen
10. Schulungs-Workshop (1-2 Stunden) mit den Schlüsselnutzern
11. Übergabeprotokoll unterschreiben
```

**Was der Kunde danach selbst kann:**
- Neue Mitarbeiter anlegen
- Templates anpassen
- Aufbewahrungsfristen konfigurieren
- Audit-Log einsehen

**Was den kaivo.studio Support braucht:**
- Größere Konfigurationsänderungen
- Migration zu anderer Version
- Performance-Tuning bei Last
- Recovery aus Backup

---

## 4. Update-Pfad

### Wenn Insilo im Markt ist

1. Wir laden neue Version (`.tgz`) in den Markt hoch
2. Olares-Box meldet "Update verfügbar"
3. Kunde-Admin entscheidet: jetzt oder zu Wartungszeit
4. Olares orchestriert Rolling-Update aller Container
5. Nach Health-Check: alte Version wird verworfen
6. Bei Fehler: automatischer Rollback

### Für Pilotkunden (vor Markt-Release)

1. Wir schicken `.tgz` per SFTP oder USB-Stick (signiert)
2. Kunde-Admin lädt es via **Upload custom chart** hoch
3. Sonst identisch zu Markt-Update

### Niemals automatisch

Wir machen niemals Auto-Updates ohne Kunden-Einwilligung. Das wäre Vertrauensbruch.

---

## 5. Backup-Strategie

### Olares-seitig (Kunde-Verantwortung)

- Olares hat eingebautes **Velero**
- Empfohlene Frequenz: täglich inkrementell, wöchentlich voll
- Backup-Ziel: Kunde-eigener NAS oder verschlüsselter S3-Bucket (extern)
- **NIEMALS** automatisches Backup in kaivo.studio-Infrastruktur

### Insilo-spezifisch

- DB-Dump-Funktion in der Admin-UI (manuell)
- Export von Meeting-Daten als ZIP (Audio + Transkript + Notiz)
- Vor jedem Major-Update wird automatisch ein Restore-Point erstellt
- Audio-Originale in MinIO werden vom Olares-Velero erfasst

---

## 6. Remote-Support

### Aktivierungsflow

1. Kunde-Admin: Settings → Support → "Remote-Support aktivieren"
2. System generiert Einmal-Token (24h gültig)
3. Tailscale-Verbindung zu kaivo.studio-Support-Server wird aufgebaut
4. Audit-Log: Eintrag mit Support-Session-ID
5. Support-Mitarbeiter loggt sich ein
6. Nach Abschluss: Admin deaktiviert (oder Auto-Ablauf)

### Während aktiv

- Support-Mitarbeiter sieht NUR Logs + Container-Status
- KEIN direkter DB-Zugriff auf User-Daten
- Jede Aktion wird im Audit-Log dokumentiert

---

## 7. Monitoring

### Auf der Box

- Olares-Dashboard: CPU, GPU, RAM, Disk, Network
- Insilo-Health-Endpoints:
  - `/health/api` — Backend
  - `/health/db` — DB-Verbindung
  - `/health/whisper` — Transkriptions-Service
  - `/health/ollama` — LLM antwortet
  - `/health/embeddings` — Embedding-Service

### An kaivo.studio

- **Standardmäßig: nichts.** Keine Telemetrie.
- **Optional:** Kunde kann Heartbeat aktivieren — sendet nur Version + Uptime + Letzter-Job, keine Inhalte.

---

## 8. Disaster Recovery

| Szenario                          | Reaktion                                      | RTO     |
|-----------------------------------|-----------------------------------------------|---------|
| Box-Hardware-Ausfall              | Replacement-Box vorkonfiguriert ausliefern   | 24h     |
| SSD-Defekt                        | Zweite SSD als Fallback (RAID)               | <1h     |
| Falsche Update-Installation       | Olares-Rollback                              | <30 Min |
| Datenverlust durch User-Fehler    | Soft-Delete: 30 Tage                         | sofort  |
| Ransomware                        | Velero-Restore                               | 4h      |
| Naturkatastrophe                  | Off-Site-Backup auf neuer Box                | 48h     |

**RPO:** 24 Stunden (tägliches Backup)
**RTO:** 4 Stunden mit Premium-SLA

---

## 9. Werkstatt-Checkliste vor Versand

```
Hardware-Seite:
□ Olares One: aktuelle OS-Version
□ Initialer Admin-Account angelegt
□ Versiegelter Briefumschlag mit Initial-Passwort
□ Verschlusssiegel-Aufkleber angebracht

Insilo-Seite:
□ App aus Markt installiert (Version-Tag dokumentiert)
□ Whisper-Modell large-v3 geladen
□ Ollama-Modell qwen2.5:14b geladen
□ BGE-M3-Modell geladen
□ Default-Org und 4 System-Templates vorhanden
□ Test-Aufnahme: durch alle Stufen erfolgreich
□ Health-Endpoints alle grün
□ Audit-Log läuft
□ Backup-Endpoint getestet

Dokumentation:
□ Quick-Start-Karte für Endnutzer
□ Admin-Handbuch für IT-Verantwortlichen
□ Übergabeprotokoll
□ Wartungsvertrag (falls vereinbart)
```
