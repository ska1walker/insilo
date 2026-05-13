# Sicherheit & Datenschutz

> Das Kernversprechen: keine Audiosekunde, kein Transkript, kein Suchindex verlässt jemals die Olares-Box.
>
> Olares OS übernimmt einen Großteil der Sicherheitsschicht. Dieses Dokument beschreibt, was Olares macht und was Insilo selbst beiträgt.

---

## 1. Was Olares automatisch leistet

| Schicht                       | Komponente bei Olares                |
|-------------------------------|--------------------------------------|
| TLS-Provisioning              | Cloudflare Tunnel / Let's Encrypt    |
| Authentifizierung             | Authelia (mit MFA-Support)           |
| Identity                      | LLDAP                                |
| Session-Management            | Authelia + Envoy-Sidecar             |
| Per-Request-Auth-Check        | Envoy-Sidecar vor jedem Pod          |
| Container-Sandboxing          | Kubernetes + AppArmor                |
| Netzwerk-Isolation            | Calico NetworkPolicy                 |
| Cross-Namespace-Block         | NetworkPolicy + system-server        |
| Disk-Verschlüsselung          | LUKS auf Olares-Storage              |
| Secret-Management             | Vault                                |
| Backup-Infrastruktur          | Velero                               |
| Remote-Access (Support)       | Tailscale / Headscale                |

**Wir müssen das nicht selbst bauen.** Das eliminiert geschätzt 30% des Code-Aufwands gegenüber einer Cloud-Lösung.

---

## 2. Was Insilo selbst beitragen muss

### Datenmodell-Sicherheit

- **Row Level Security (RLS)** auf jeder Tabelle mit Org-Daten
- **Soft-Delete** als Default (30 Tage Wiederherstellungsfrist)
- **Audit-Log** für alle sicherheitsrelevanten Aktionen
- **Verschlüsselung sensibler Felder** mit `pgcrypto`

### Eingabe-Validierung

- Pydantic-Modelle mit `extra='forbid'`
- File-Upload: Mime-Validation, Magic-Bytes-Check, Max-Size
- SQL-Injection: parametrisierte Queries via SQLAlchemy
- XSS: React-Default-Escaping, kein `dangerouslySetInnerHTML`

### LLM-Sicherheit

- Prompt-Injection-Schutz: User-Input strikt im User-Slot, System-Prompt fest
- Output-Validierung: Pydantic-Schema-Match
- Keine Code-Execution aus LLM-Output

### Retention

| Datentyp                    | Standard-Aufbewahrung    | Konfigurierbar |
|-----------------------------|--------------------------|----------------|
| Audio-Originale             | 90 Tage                  | ja, pro Org    |
| Transkripte                 | unbegrenzt               | ja             |
| Zusammenfassungen           | unbegrenzt               | ja             |
| Audit-Logs                  | 3 Jahre                  | nein           |
| Soft-Deleted Records        | 30 Tage                  | nein           |

---

## 3. DSGVO-Compliance

### Rollenverteilung

- **Verantwortlicher** im DSGVO-Sinne: der Kunde (Box-Betreiber)
- **Auftragsverarbeiter:** keiner (alles on-prem)
- **Drittlandtransfer:** entfällt
- **AVV:** entfällt zwischen kaivo.studio und Kunde, soweit kein Remote-Support stattfindet

### Betroffenenrechte (Art. 15-22 DSGVO)

| Recht                   | Umsetzung                                      |
|-------------------------|------------------------------------------------|
| Auskunft (Art. 15)      | Export-Funktion: alle Daten zu User-ID als JSON|
| Berichtigung (Art. 16)  | UI-Funktion zum Editieren persönlicher Daten   |
| Löschung (Art. 17)      | Hard-Delete-Funktion                           |
| Datenübertragbarkeit    | JSON-Export aller Meetings + Transkripte       |
| Widerspruch             | Keine Verarbeitung ohne User-Anstoß            |

---

## 4. Audit-Log

```sql
CREATE TABLE audit_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp    TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id      UUID,
  olares_user  TEXT,           -- aus X-Bfl-User
  org_id       UUID,
  action       TEXT NOT NULL,
  resource_type TEXT,
  resource_id  UUID,
  ip_address   INET,
  user_agent   TEXT,
  changes      JSONB,
  success      BOOLEAN NOT NULL
);
```

**Geloggte Events:**
- Login-Versuche (von Authelia über Webhook)
- Datei-Uploads
- Meeting-CRUD-Operationen
- Template-Änderungen
- Admin-Aktionen
- Remote-Support-Sessions

**Unveränderlich:** Append-only. RLS-Policy blockiert UPDATE/DELETE.

---

## 5. Bekannte Angriffsvektoren & Schutzmaßnahmen

| Vektor                         | Schutz                                                       |
|--------------------------------|--------------------------------------------------------------|
| Direkter Pod-Zugriff           | Olares NetworkPolicy blockiert Cross-Namespace               |
| Auth-Bypass                    | Envoy-Sidecar prüft jeden Request                            |
| SQL Injection                  | SQLAlchemy parametrisierte Queries                           |
| IDOR                           | RLS in PostgreSQL                                            |
| Mass Assignment                | Pydantic `extra='forbid'`                                    |
| File Upload Attacks            | Mime + Magic Bytes + Size Limit                              |
| XSS                            | React Auto-Escape, Strict CSP                                |
| Prompt Injection (LLM)         | System-Prompt fest, User-Input nur in user-Slot              |
| Model-Output-Leakage           | Pydantic-validierte JSON-Schemas                             |

---

## 6. Was wir bewusst NICHT tun

- ❌ Keine Telemetrie, auch nicht "anonymisiert"
- ❌ Kein Crash-Reporting an externe Services
- ❌ Keine externen CDNs in Production (Fonts/Icons self-hosted)
- ❌ Kein externer E-Mail-Provider (Olares-interner SMTP-Relay)
- ❌ Kein Auto-Backup in fremde Cloud
- ❌ Keine "Phone Home"-Heartbeats

`OlaresManifest.yaml.options.allowedOutboundPorts: []` — wir deklarieren explizit, dass keine ausgehenden Verbindungen erlaubt sind.

---

## 7. Incident Response

**Bei Verdacht auf Sicherheitsvorfall:**

1. **Sofort:** Box vom Netz nehmen (Kunde) oder Tailscale-Zugriff sperren
2. **Innerhalb 24h:** Forensische Audit-Log-Analyse
3. **Innerhalb 72h:** Meldung an Aufsichtsbehörde (falls personenbezogene Daten betroffen)
4. **Information an Betroffene:** falls hohes Risiko (Art. 34 DSGVO)
5. **Post-Mortem**

**Kontakt:** security@kaivo.studio (PGP-Key veröffentlicht)

---

## 8. Zertifizierungen

| Phase | Zertifizierung                              | Status      |
|-------|---------------------------------------------|-------------|
| 5     | DSGVO-Konformitätserklärung (intern)        | Phase 4 nötig |
| 6     | TÜV-Süd "Datenschutz geprüft"               | optional, Q3 2027 |
| 7+    | ISO 27001                                   | bei Bedarf  |

**Vorerst:** Wir verlassen uns auf das *technische* Versprechen und Audit-Log, nicht auf Papier-Zertifikate. Das ist der ehrlichere Pitch — und der einzige, der die "Daten verlassen das Haus nicht"-Aussage glaubhaft macht.
