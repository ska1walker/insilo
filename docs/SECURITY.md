# Sicherheit & Datenschutz

> Das Kernversprechen des Produkts ist Datensouveränität. Dieses Dokument hält fest, *wie* wir dieses Versprechen einlösen — und gegen welche Schwachstellen wir uns aktiv schützen.

---

## 1. Versprechen an den Kunden

> **Keine einzige Sekunde Audio, kein Transkript, kein Suchindex verlässt jemals die Olares-Box des Kunden.**

Dieses Versprechen ist absolut. Es ist das Verkaufsargument gegen PLAUD, Otter, Fireflies, Microsoft Copilot und alle Cloud-Anbieter. Jede Entscheidung im System wird daran gemessen.

---

## 2. DSGVO-Compliance-Architektur

### Datenverarbeitung

- **Verantwortlicher** im DSGVO-Sinne: der Kunde (Box-Betreiber)
- **Auftragsverarbeiter:** keiner — alles läuft on-prem
- **Drittlandtransfer:** entfällt, da keine Cloud genutzt wird
- **AVV (Auftragsverarbeitungsvertrag):** entfällt zwischen kaivo.studio und Kunde, soweit kaivo.studio nicht in Wartung/Support involviert ist
- **Bei Remote-Support:** AVV wird abgeschlossen, Audit-Log dokumentiert Zugriffe

### Betroffenenrechte (Art. 15-22 DSGVO)

| Recht                   | Umsetzung                                      |
|-------------------------|------------------------------------------------|
| Auskunft (Art. 15)      | Export aller Daten zu User-ID als JSON         |
| Berichtigung (Art. 16)  | UI-Funktion zum Editieren persönlicher Daten   |
| Löschung (Art. 17)      | Hard-Delete-Funktion (überschreibt Soft-Delete)|
| Datenübertragbarkeit    | JSON-Export aller Meetings + Transkripte       |
| Widerspruch             | Keine Verarbeitung außer auf User-Anstoß       |

### Aufbewahrungsfristen

- **Audio-Originale:** 90 Tage nach Aufnahme (konfigurierbar pro Org)
- **Transkripte:** unbegrenzt (oder per Policy)
- **Zusammenfassungen:** unbegrenzt
- **Audit-Logs:** 3 Jahre (Compliance-relevant)
- **Soft-Deleted Records:** 30 Tage, dann Hard-Delete

---

## 3. Verschlüsselung

### Transport

- **PWA ↔ Box:** TLS 1.3, automatisch provisioniert durch Olares
- **Box-interne Services:** TLS zwischen Containern (mTLS optional)
- **Remote-Support:** Tailscale (WireGuard-basiert)

### At-Rest

- **PostgreSQL:** Disk-Verschlüsselung über LUKS auf Olares-Storage
- **Audio-Dateien:** Server-Side-Encryption in Supabase Storage
- **Sensible Felder** (z.B. API-Tokens, Org-Settings): `pgcrypto` zusätzlich

### Schlüsselverwaltung

- Olares stellt Infisical als Secret-Manager bereit
- Keys werden nicht in Git committed (`.env.example` als Template)
- Master-Key für Box-Backups: nur beim Kunden-Admin

---

## 4. Authentifizierung & Autorisierung

### Authentifizierung

- **Standard:** E-Mail + Passwort über Supabase Auth (lokal auf der Box)
- **Magic Link:** Möglich, via lokalem SMTP-Relay (NIE externer Mail-Provider)
- **SSO (optional):** Olares ID System
- **2FA Pflicht** für Admin-Rollen (TOTP)
- **Passwort-Policy:** mindestens 12 Zeichen, gemischte Zeichenklassen

### Autorisierung

- **Row Level Security** in PostgreSQL — jede Tabelle hat RLS aktiviert
- **Rollen** (per `user_org_roles`-Tabelle):
  - `owner` — Vollzugriff inkl. Org-Settings
  - `admin` — User-Management, alle Meetings
  - `member` — eigene Meetings + geteilte
  - `viewer` — nur Lesezugriff auf geteilte Meetings

### Mandanten-Trennung

- Jede Tabelle, die Org-Daten enthält, hat `org_id` als FK
- RLS-Policy stellt sicher: User sieht nur Daten seiner Org(s)
- Box kann mehrere Orgs hosten (z.B. Holdings, Beratungen mit Mandanten)
- Audit-Log ist mandantenübergreifend für Admin sichtbar

---

## 5. Audit-Log

**Jede** sicherheitsrelevante Aktion wird geloggt:

```sql
CREATE TABLE audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id     UUID REFERENCES users(id),
  org_id      UUID REFERENCES orgs(id),
  action      TEXT NOT NULL,        -- 'login', 'meeting.create', 'user.delete', ...
  resource_type TEXT,                -- 'meeting', 'user', 'template', ...
  resource_id UUID,
  ip_address  INET,
  user_agent  TEXT,
  changes     JSONB,                 -- Diff: {before: {...}, after: {...}}
  success     BOOLEAN NOT NULL
);
```

**Geloggte Events:**
- Logins (Erfolg & Misserfolg)
- Datei-Uploads
- Meeting-Erstellung, -Edit, -Löschung
- User-Verwaltung
- Template-Änderungen
- Admin-Aktionen
- Remote-Support-Sessions

**Wer sieht was:**
- User: eigene Aktionen
- Admin: alle Aktionen seiner Org
- Owner: alle Aktionen + System-Events

**Unveränderlichkeit:** Audit-Log ist append-only. Keine UPDATE/DELETE-Rechte auf der Tabelle für normale User.

---

## 6. Bekannte Angriffsvektoren & Schutzmaßnahmen

### Browser-Side

| Vektor                         | Schutz                                              |
|--------------------------------|-----------------------------------------------------|
| XSS                            | Strict CSP, React-Default-Escaping, kein dangerouslySetInnerHTML |
| CSRF                           | SameSite-Cookies, CSRF-Tokens für mutating ops      |
| Clickjacking                   | X-Frame-Options: DENY                               |
| Local Storage Theft            | Auth-Tokens in httpOnly Cookies, keine sensitive Data in localStorage |

### API-Side

| Vektor                         | Schutz                                              |
|--------------------------------|-----------------------------------------------------|
| SQL Injection                  | Parametrized Queries via Supabase Client, keine String-Konkatenation |
| IDOR (Insecure Direct Object Reference) | RLS in PostgreSQL — User können nur eigene Daten sehen |
| Mass Assignment                | Pydantic-Modelle mit `extra='forbid'`               |
| Rate Limiting                  | FastAPI-Middleware mit Redis-Backend                |
| Brute Force Login              | Exponential Backoff via Supabase                    |
| File Upload Attacks            | Mime-Validation, Magic-Bytes-Check, Max-Size, AV-Scan optional |

### Infrastruktur

| Vektor                         | Schutz                                              |
|--------------------------------|-----------------------------------------------------|
| Container-Escape               | Olares-Sandboxing (Kubernetes + AppArmor)           |
| Network-Lateral-Movement       | Olares isoliert Services per Netzwerk-Policy        |
| Supply-Chain (deps)            | Lock-Files, Dependabot, regelmäßige Audits          |
| Update-Tampering               | Signierte Update-Pakete (Sigstore/Cosign)           |

### KI-spezifisch

| Vektor                         | Schutz                                              |
|--------------------------------|-----------------------------------------------------|
| Prompt Injection               | Template-System nutzt System-Prompts, User-Input strikt im User-Slot |
| Model-Output-Leakage           | Output wird Pydantic-validiert, keine arbitrary code execution |
| Training-Data-Extraction       | Modelle sind read-only, kein Fine-Tuning auf Kundendaten ohne explizite Erlaubnis |

---

## 7. Penetration-Testing & Code-Review

- **Vor jeder produktiven Auslieferung:** Code-Review durch Maintainer
- **Phase 4 Meilenstein:** Externes Pentest (vor Pilotkunde)
- **Phase 6 ff.:** Jährliches Pentest oder bei Major-Release
- **Bug Bounty:** wird erwogen ab >10 Kunden

---

## 8. Incident Response

### Bei Verdacht auf Sicherheitsvorfall:

1. **Sofort:** Box vom Netz nehmen (Kunde) ODER Tailscale-Zugriff sperren (kaivo.studio)
2. **Innerhalb 24h:** Forensische Analyse der Audit-Logs
3. **Innerhalb 72h:** Meldung an Aufsichtsbehörde (falls personenbezogene Daten betroffen, Art. 33 DSGVO)
4. **Information an Betroffene:** falls hohes Risiko (Art. 34 DSGVO)
5. **Post-Mortem:** Public oder intern, Lehren in Backlog

### Kontaktwege:

- **Kunde meldet Vorfall:** security@kaivo.studio (PGP-Key auf Website)
- **kaivo.studio meldet Vorfall:** vertraglich vereinbarter Hauptansprechpartner

---

## 9. Was wir bewusst NICHT tun

- ❌ **Keine Telemetrie**, auch nicht "anonymisiert"
- ❌ **Kein Crash-Reporting** an Drittservices wie Sentry (wenn dann self-hosted)
- ❌ **Keine externen CDNs** in Production (Fonts, Icons werden self-hosted)
- ❌ **Keine externen Tracking-Tools**
- ❌ **Keine "Phone Home"-Heartbeats**
- ❌ **Kein Auto-Backup in fremde Cloud**
- ❌ **Kein E-Mail-Versand über externe Provider** (lokaler SMTP-Relay)

Jede dieser Verlockungen wäre technisch praktisch — aber sie alle würden das Kernversprechen aushöhlen. Wir verzichten konsequent.

---

## 10. Zertifizierungs-Roadmap

Ab welcher Phase welche Zertifizierung sinnvoll wird:

| Phase | Zertifizierung                              | Aufwand    | Nutzen                              |
|-------|---------------------------------------------|------------|-------------------------------------|
| 5     | DSGVO-Konformitätserklärung (intern)        | klein      | Verkaufsdoku                        |
| 6     | TÜV-Süd "Datenschutz geprüft"               | mittel     | Vertrauenssignal für Mittelstand    |
| 7+    | ISO 27001                                   | hoch       | Pflicht für größere Kunden          |
| 7+    | BSI C5                                      | sehr hoch  | Nur wenn Behörden-Kunden ansteht    |

**Vorerst:** Wir verlassen uns auf das *technische* Versprechen und das Audit-Log, nicht auf Papier-Zertifikate. Das ist der ehrlichere Pitch.
