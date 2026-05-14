# Insilo Webhooks — Vertrag

> **Zielgruppe:** Entwicklerinnen und Entwickler, die Insilo an ein Drittsystem anschließen (Duo, OpenWebUI, Notion, eigene Integrationen).
> **Stand:** Mai 2026
> **Verwandt:** [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md)

---

## 1. Übersicht

Insilo schickt nach Meeting-Lifecycle-Ereignissen signierte HTTP-POST-Requests an die in `/einstellungen → Webhooks` registrierten URLs. Die Webhooks sind **push-only**: Insilo sendet, der Empfänger antwortet mit `2xx`. Es gibt keinen Pull-Endpoint und keine Cloud-Vermittlung — der POST geht direkt von der Olares-Box des Kunden an das vom Kunden angegebene Ziel.

**Charakteristika:**

- Transport: HTTPS oder HTTP (HTTPS dringend empfohlen — Insilo signiert zwar, aber das Markdown ist nicht verschlüsselt).
- Format: JSON, UTF-8.
- Authentifizierung: HMAC-SHA256 über den **rohen Request-Body** mit einem geteilten Secret.
- Idempotenz: jede Auslieferung hat eine stabile UUID im Header `X-Insilo-Delivery-ID`, die über Retries identisch bleibt.
- Retry: max. zwei Wiederholungen bei `5xx` / Timeout / Verbindungsfehler. Bei `4xx` keine Retry.

---

## 2. Events

| Event | Wann er feuert | Enthält `markdown`? | Quelle im Backend |
|---|---|---|---|
| `meeting.created` | Sobald ein Meeting in Insilo angelegt wird (Upload abgeschlossen) | nein | `routers/meetings.py` |
| `meeting.ready` | Nach erfolgreicher Transkription + Zusammenfassung | **ja** | `tasks/summarize.py` |
| `meeting.failed` | Transkription oder Summary ist fehlgeschlagen | nein | `tasks/transcribe.py`, `tasks/summarize.py` |
| `meeting.updated` | Titel, Beschreibung oder Tags wurden geändert | nein | `routers/meetings.py`, `routers/tags.py` |
| `meeting.deleted` | Meeting wurde soft-gelöscht | nein | `routers/meetings.py` |

Zusätzlich existiert das **Diagnose-Event** `test.ping`, das ausschließlich beim Drücken des „Testen"-Buttons im WebhookManager gesendet wird (siehe §9).

---

## 3. Header

Jeder POST-Request enthält folgende Header:

| Header | Beispiel | Bedeutung |
|---|---|---|
| `Content-Type` | `application/json; charset=utf-8` | Body-Format |
| `User-Agent` | `Insilo-Webhook/1.0` | Identifikation des Senders |
| `X-Insilo-Event` | `meeting.ready` | Event-Typ (s. §2) |
| `X-Insilo-Delivery-ID` | `8a1b2c3d4e5f6...` (32-stelliger UUID-Hex) | Stabiler Idempotenz-Schlüssel — bleibt über Retries identisch |
| `X-Insilo-Signature` | `sha256=ab12...ef34` | HMAC-SHA256 des rohen Body, hex-encoded |

---

## 4. Signatur-Verfahren

Insilo signiert den **rohen Request-Body** (Bytes, exakt so wie er über die Leitung geht) mit HMAC-SHA256 unter Verwendung des bei der Webhook-Anlage erzeugten Secrets:

```
signature = "sha256=" + hex( HMAC_SHA256(secret_bytes, raw_body_bytes) )
```

Wichtig für die Verifikation auf Empfänger-Seite:

1. **Über den rohen Body hashen, nicht über das geparste JSON.** Whitespace, Schlüssel-Reihenfolge oder Re-Serialisierung verändern das Hash.
2. **Den Vergleich timing-safe machen** (`hmac.compare_digest` in Python, `crypto.timingSafeEqual` in Node). Naiver `==`-Vergleich leakt Bits über Timing.
3. **Bei Fehlschlag mit `401` antworten** — Insilo wertet das als Client-Fehler und retried nicht.

Das Secret wird beim Anlegen des Webhooks in Insilo **einmalig angezeigt**. Bei Verlust muss der Webhook gelöscht und neu angelegt werden, oder das Secret rotiert (PUT `/api/v1/webhooks/{id}` mit neuem `secret`).

---

## 5. Body-Struktur

Gemeinsamer Rahmen für alle Events:

```json
{
  "id": "8a1b2c3d4e5f67890abcdef123456789",
  "event": "meeting.ready",
  "occurred_at": "2026-05-14T18:23:11.812345+00:00",
  "meeting": {
    "id": "f1e2d3c4-b5a6-7890-1234-567890abcdef",
    "org_id": "01HQ...",
    "title": "Strategie Q2",
    "status": "ready",
    "recorded_at": "2026-05-14T14:30:00+00:00",
    "duration_sec": 1800,
    "language": "de",
    "template_id": "01HR...",
    "template_name": "Allgemeine Besprechung",
    "error_message": null,
    "deleted_at": null,
    "tags": ["Strategie", "Mandant Müller"]
  }
}
```

`id` (= `X-Insilo-Delivery-ID`) ist eine UUID-Hex und ist über Retries derselben Auslieferung **stabil**. Verschiedene Subscriber für dasselbe Meeting bekommen verschiedene `id`s.

### 5.1 `meeting.ready` — zusätzliche Felder

Nur bei `meeting.ready`:

```json
{
  ...,
  "markdown": "---\nsource: insilo\nmeeting_id: f1e2d3c4-...\ntitle: Strategie Q2\n...\n---\n\n# Strategie Q2\n\n...",
  "summary": {
    "content": { "...": "Template-spezifisch — JSON-Struktur folgt dem Template" },
    "llm_model": "qwen2.5:14b-instruct-q4_K_M"
  }
}
```

Das `markdown`-Feld ist die **vorrangige Verarbeitungsgrundlage** für Drittsysteme. Es enthält:

- YAML-Frontmatter (`source`, `meeting_id`, `title`, `date`, `duration_min`, `template`, `language`, `tags`, `speakers`)
- H1-Titel
- Metazeile (Datum, Dauer, Sprache)
- Template-definierte H2-Sektionen aus dem Summary-JSON
- GFM-Checklisten für Aufgaben (`- [ ] Aufgabentext — Verantwortlich, Frist`)
- Vollständiges Transkript mit Zeitstempeln und Speaker-Labels

Die `summary.content`-Struktur ist optional und gibt Drittsystemen Zugriff auf die strukturierten Felder, falls das Markdown nicht ausreicht.

### 5.2 Andere Events

`meeting.created` / `meeting.updated` / `meeting.deleted`: kein `markdown`, kein `summary`. Der `meeting`-Block enthält die aktuellen Metadaten zum Zeitpunkt des Events.

`meeting.failed`: `meeting.status === "failed"`, `meeting.error_message` enthält die Fehlerursache (z. B. `"transcription_failed: invalid audio format"`).

---

## 6. Empfänger-Pseudocode

### 6.1 Python (FastAPI / Flask)

```python
import hmac
import hashlib
import json

INSILO_SECRET = b"..."  # aus Insilo kopiert

def verify_signature(raw_body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(INSILO_SECRET, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)

def handle_webhook(request):
    raw = request.body                        # raw bytes, NICHT request.json()
    sig = request.headers.get("X-Insilo-Signature", "")
    if not verify_signature(raw, sig):
        return Response(status=401)

    delivery_id = request.headers["X-Insilo-Delivery-ID"]
    if already_processed(delivery_id):
        return Response(status=200)           # idempotente Re-Delivery

    payload = json.loads(raw)
    event = payload["event"]
    meeting_id = payload["meeting"]["id"]

    if event == "meeting.ready":
        upsert_note(
            external_source="insilo",
            external_id=meeting_id,
            title=payload["meeting"]["title"],
            body_markdown=payload["markdown"],
            tags=payload["meeting"]["tags"],
        )
    elif event == "meeting.updated":
        patch_note_metadata(
            external_source="insilo",
            external_id=meeting_id,
            title=payload["meeting"]["title"],
            tags=payload["meeting"]["tags"],
        )
    elif event == "meeting.deleted":
        soft_delete_note(external_source="insilo", external_id=meeting_id)
    elif event == "meeting.failed":
        notify_user_of_failure(meeting_id, payload["meeting"]["error_message"])
    # meeting.created und test.ping können ignoriert werden

    mark_processed(delivery_id)
    return Response(status=200)
```

### 6.2 Node.js (Express)

```js
import crypto from "node:crypto";
import express from "express";

const INSILO_SECRET = process.env.INSILO_SECRET;
const app = express();

// WICHTIG: raw body parsen, NICHT express.json() vorschalten
app.post(
  "/api/integrations/insilo",
  express.raw({ type: "application/json" }),
  (req, res) => {
    const raw = req.body; // Buffer
    const sigHeader = req.header("X-Insilo-Signature") || "";
    const expected =
      "sha256=" +
      crypto.createHmac("sha256", INSILO_SECRET).update(raw).digest("hex");

    const sigBuf = Buffer.from(sigHeader);
    const expBuf = Buffer.from(expected);
    if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) {
      return res.status(401).end();
    }

    const deliveryId = req.header("X-Insilo-Delivery-ID");
    if (alreadyProcessed(deliveryId)) return res.status(200).end();

    const payload = JSON.parse(raw.toString("utf8"));
    // ... wie oben ...
    markProcessed(deliveryId);
    res.status(200).end();
  }
);
```

---

## 7. Idempotenz

Insilo garantiert **at-least-once delivery** — derselbe Event kann mehrfach beim Empfänger eintreffen, wenn:

- der erste Versuch mit `5xx` / Timeout endete und Insilo retried (1-2 weitere Versuche),
- der Empfänger `2xx` antwortete, die Antwort aber nicht zurückkam,
- der Benutzer in Insilo „Retry Summary" auslöst (führt zu neuem `meeting.ready` mit **neuer** `delivery_id`).

**Empfehlung:** Pflegen Sie eine Tabelle `processed_webhook_deliveries(delivery_id text primary key, received_at timestamptz default now())`. Vor der Verarbeitung prüfen, ob `delivery_id` schon vorhanden ist; nach erfolgreicher Verarbeitung einfügen. Alte Einträge können nach 7 Tagen aufgeräumt werden — länger retried Insilo nicht.

Für `meeting.ready`-Updates (Re-Summary) empfiehlt sich zusätzlich ein **Upsert auf `(external_source, external_id)`** mit `external_source = "insilo"` und `external_id = meeting.id`. Eine erneute `meeting.ready` für dasselbe Meeting hat dann eine neue `delivery_id` (Insilo betrachtet es als neuen Event), überschreibt aber den existierenden Note statt ein Duplikat anzulegen.

Beispiel-Migration für den Empfänger:

```sql
alter table notes add column external_source text;
alter table notes add column external_id text;
create unique index notes_external_idx on notes (external_source, external_id);

create table processed_webhook_deliveries (
  delivery_id text primary key,
  received_at timestamptz not null default now()
);
```

---

## 8. Retry-Policy

| Antwort des Empfängers | Insilos Reaktion |
|---|---|
| `2xx` | Erfolg. `last_success_at` wird aktualisiert. Kein Retry. |
| `4xx` | Client-Fehler. `last_failure_at` + `last_failure_msg` aktualisiert. **Kein Retry** — die Signatur stimmt nicht oder die URL handelt das Event nicht. |
| `5xx`, Timeout (>10 s), Verbindungsfehler | Retry mit Exponential Backoff. Max. zwei Wiederholungen. |

Backoff-Zeiten:

- Versuch 1 → sofort
- Versuch 2 → nach 30 s
- Versuch 3 → nach 90 s

Nach drei erfolglosen Versuchen wird das Event **endgültig aufgegeben**. Es gibt keinen separaten Alert — der Status ist im WebhookManager (rote LED + `last_failure_msg`) sichtbar und in der Tabelle `webhook_deliveries` historisiert.

**Empfehlung für den Empfänger:** antworten Sie schnell (innerhalb von 2 s) mit `2xx` nach Validierung + Enqueue in Ihre interne Queue. Lange Antwortzeiten provozieren Timeouts und unnötige Retries.

---

## 9. `test.ping`

Beim Klick auf „Testen" im WebhookManager schickt Insilo **synchron** einen Diagnose-POST:

```json
{
  "id": "abc123...",
  "event": "test.ping",
  "occurred_at": "2026-05-14T18:23:11.812345+00:00",
  "message": "Testlieferung von Insilo — alles in Ordnung."
}
```

Eigenschaften:

- Header sind identisch zu Lifecycle-Events (mit `X-Insilo-Event: test.ping`).
- **Keine Retry** — der Benutzer sieht das Ergebnis (Status-Code, Antwort-Auszug, Elapsed-Zeit) sofort im UI.
- Wird **nicht** in `webhook_deliveries` historisiert.
- Empfänger sollten den Event ignorieren (oder loggen) und mit `200` antworten.

---

## 10. Feld-Garantien

Welche Felder sind in welchem Event garantiert?

| Feld | `created` | `ready` | `failed` | `updated` | `deleted` |
|---|---|---|---|---|---|
| `id`, `event`, `occurred_at` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `meeting.id`, `meeting.org_id`, `meeting.title`, `meeting.status` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `meeting.recorded_at`, `meeting.duration_sec`, `meeting.language` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `meeting.template_id`, `meeting.template_name` | optional | ✓ | optional | ✓ | optional |
| `meeting.tags` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `meeting.error_message` | null | null | **gefüllt** | null | null |
| `meeting.deleted_at` | null | null | null | null | **gefüllt** |
| `markdown` | — | **✓** | — | — | — |
| `summary` | — | **✓** | — | — | — |

„optional" = vorhanden, wenn der Nutzer ein Template gewählt hat; sonst `null`.

---

## 11. Konfigurations-Ablauf für Endnutzer

1. **In Insilo (`/einstellungen` → Webhooks → „Neuen Webhook hinzufügen"):**
   - URL des Drittsystems eintragen
   - Events auswählen (Minimum: `meeting.ready`)
   - Speichern → das Secret wird **einmalig** angezeigt → kopieren
2. **Im Drittsystem (z. B. Duo):**
   - Secret einfügen
   - Zielordner / Tabelle / Verarbeitungspfad konfigurieren
3. **Test:** im Insilo-WebhookManager auf „Testen" klicken → das Drittsystem sollte `200` zurückgeben → grüne LED erscheint.

---

## 12. Sicherheitshinweise

- **Niemals das Secret im Klartext loggen** — weder im Drittsystem noch in Insilo. Insilo speichert es verschlüsselt in `org_webhooks.secret`.
- **HTTPS-Endpunkte bevorzugen.** Bei HTTP geht der Body unverschlüsselt durchs Netz; die Signatur schützt vor Manipulation, nicht vor Mitlesen.
- **Webhook-Empfänger sind nicht öffentlich exponiert.** Wenn das Drittsystem hinter einer Firewall steht, muss die Olares-Box den Empfänger erreichen können — typisches Setup ist beide im selben VPN / Tailnet.
- **Rate-Limit auf der Empfänger-Seite.** Insilo kennt selbst kein Rate-Limit pro Webhook — bei vielen gleichzeitigen Meetings können viele POSTs gleichzeitig eintreffen.

---

## 13. Versionierung

Die hier dokumentierte Vertrags-Version ist `1.0`. Der `User-Agent`-Header (`Insilo-Webhook/1.0`) gibt die Vertrags-Version mit aus. Künftige Breaking Changes erhöhen die Major-Version und werden parallel zur alten Version eine Übergangszeit lang ausgeliefert.
