# Insilo — Handbuch

Für Nutzerinnen, Nutzer und die Person, die Insilo auf der Box betreut.
Stand: 6. September 2026, Fassung 0.1.87.

> Die übrigen Dateien in `docs/` sind Werkstattmaterial. Dieses Handbuch
> ist das einzige, das für den Betrieb beim Kunden geschrieben ist.

---

## Inhalt

1. [Was Insilo tut](#1-was-insilo-tut)
2. [Installieren](#2-installieren)
3. [Einmalig einrichten](#3-einmalig-einrichten)
4. [Der tägliche Weg](#4-der-tägliche-weg)
5. [Löschen, Papierkorb, Fristen](#5-löschen-papierkorb-fristen)
6. [Was für die Datenschutzprüfung bereitsteht](#6-was-für-die-datenschutzprüfung-bereitsteht)
7. [Anschluss an andere Systeme](#7-anschluss-an-andere-systeme)
8. [Sichern und wiederherstellen](#8-sichern-und-wiederherstellen)
9. [Aktualisieren](#9-aktualisieren)
10. [Wenn etwas nicht geht](#10-wenn-etwas-nicht-geht)
11. [Was Insilo nicht tut](#11-was-insilo-nicht-tut)

---

## 1. Was Insilo tut

Insilo nimmt Besprechungen auf, schreibt sie mit und fasst sie zusammen.
Die Anwendung läuft auf **Ihrer** Olares-Box, im eigenen Haus.

In der Vorgabe verlässt nichts diese Maschine: die Tonaufnahme liegt
darauf, die Spracherkennung läuft darauf, der Suchindex liegt darauf.

Zwei Dinge können das ändern, und beide tragen Sie selbst ein:

- ein **Sprachmodell** an einer fremden Adresse — dann geht das
  *Transkript* zur Zusammenfassung dorthin;
- eine **Spracherkennung** an einer fremden Adresse — dann geht die
  *Tonaufnahme selbst* dorthin.

Beides steht danach im Datenschutz-Nachweis, mit gemessener Menge
(Abschnitt 6). Der Suchindex bleibt in jeder Einrichtung auf der Box.

---

## 2. Installieren

### Aus dem Olares-Markt

1. Olares-Schreibtisch öffnen
2. **Market** → nach „Insilo" suchen
3. **Install**, die angeforderten Berechtigungen bestätigen
4. Fünf bis zehn Minuten warten — beim ersten Start lädt der
   Spracherkennungs-Dienst sein Modell
5. Insilo erscheint als Kachel auf dem Schreibtisch

### Aus einer gelieferten Datei

Solange Insilo nicht im öffentlichen Markt steht, kommt es als
`.tgz`-Datei:

1. **Market** → **My Olares** → **Upload custom chart**
2. Datei wählen, Prüfung abwarten, **Install now**

### Der erste Zugang

> **Das braucht heute noch eine Hand an der Datenbank.** Insilo hat keine
> eigene Anmeldung — die macht Olares — und legt seit Fassung 0.1.85
> **niemanden mehr von selbst an**. Das war eine bewusste Entscheidung:
> vorher bekam jeder ausgedachte Name eine frische Organisation und war
> darin Inhaber. Ein Einrichtungsdialog, der die erste Person eintragen
> würde, fehlt aber noch. Bis dahin bleibt der erste Aufruf einer frisch
> installierten Box bei
> *„Unknown identity. Ask an administrator to add this user."*

Die erste Person und ihre Organisation eintragen — einmal, mit dem
Olares-Benutzernamen, unter dem sie sich anmeldet:

```bash
kubectl exec -n os-platform citus-0 -- psql -U olares -d <db-name> <<'SQL'
with o as (
  insert into public.orgs (name, slug)
  values ('Kanzlei Muster', 'kanzlei-muster')
  returning id
), u as (
  insert into public.users (olares_username, display_name)
  values ('vorname', 'Vorname Nachname')
  returning id
)
insert into public.user_org_roles (user_id, org_id, role)
select u.id, o.id, 'owner' from u, o;
SQL
```

Den Datenbanknamen liefert `DB_NAME` im Backend-Deployment.

Nur bei einer **wirklich neuen** Box nötig. Wird Insilo auf einer Box neu
installiert, auf der es schon lief, holt es Organisation und Personen aus
dem Abzug in `/app/data` zurück (Abschnitt 8).

### Weitere Personen

Kolleginnen und Kollegen legen Sie **in Olares** an — Insilo baut keine
zweite Benutzerverwaltung daneben. Damit sie dieselben Besprechungen
sehen, brauchen sie danach eine Zeile in derselben Organisation:

```bash
kubectl exec -n os-platform citus-0 -- psql -U olares -d <db-name> <<'SQL'
with u as (
  insert into public.users (olares_username, display_name)
  values ('kollegin', 'Vorname Nachname')
  on conflict (olares_username) do update set display_name = excluded.display_name
  returning id
)
insert into public.user_org_roles (user_id, org_id, role)
select u.id, o.id, 'member'
from u, public.orgs o
where o.slug = 'kanzlei-muster';
SQL
```

Vier Rollen gibt es: `owner`, `admin`, `member`, `viewer`. Die ersten
beiden sehen im Protokoll die Vorgänge **aller** Personen der
Organisation, die anderen nur die eigenen.

---

## 3. Einmalig einrichten

Alles unter **Einstellungen** in der linken Leiste.

### 3.1 Sprachmodell (nötig für Zusammenfassungen)

Aufnahme und Transkription laufen sofort. Zusammenfassungen brauchen ein
Sprachmodell, und Insilo bringt bewusst keines mit — sonst läge ein
zweites Vier-Gigabyte-Abbild auf der Box, das viele Kunden gar nicht
benutzen.

Üblich ist die **LiteLLM-App auf derselben Box**:

1. LiteLLM auf dem Olares-Schreibtisch öffnen
2. Die Adresse aus der Adresszeile kopieren, sie endet auf `/v1`
3. In Insilo unter **Einstellungen → Sprachmodell** eintragen,
   Modellnamen dazu (z. B. `chat`)
4. **Verbindung testen** — der Test sagt Ihnen, ob die Adresse trägt

Jeder OpenAI-kompatible Endpunkt funktioniert. Steht er außerhalb Ihres
Hauses, geht das Transkript dorthin; Insilo sagt das dann auf der
Aufnahmeseite und im Datenschutz-Nachweis, ohne dass Sie danach suchen
müssen.

### 3.2 Spracherkennung (nur ändern, wenn Sie es wollen)

Bleibt das Feld leer, transkribiert der mitgelieferte Dienst auf dieser
Box — dann verlässt **keine Tonaufnahme** das Haus. Das ist die Vorgabe
und für die meisten Kanzleien die richtige.

Tragen Sie hier eine Adresse ein, geht die Tonaufnahme selbst dorthin.
Auf einer Adresse derselben Box bleibt sie auf derselben Maschine, bei
einem fremden Anbieter nicht. Wenn Sie eine Adresse eintragen, brauchen
Sie auch die **Modell-ID** — ohne sie lehnt der Endpunkt jede Anfrage ab,
die Aufnahme läuft dann, die Transkription nicht.

### 3.3 Sprache

Insilo spricht Deutsch, Englisch, Französisch, Spanisch und Italienisch.
Die gewählte Sprache gilt für die Oberfläche **und** für die
Zusammenfassungen — auch wenn die Besprechung in einer anderen Sprache
geführt wurde. Die Aufnahmesprache stellen Sie pro Aufnahme getrennt ein.

### 3.4 Vorlagen für Zusammenfassungen

Jede Vorlage steuert über einen Anweisungstext, wie das Sprachmodell das
Transkript ordnet — welche Abschnitte es bildet, in welcher Sprache es
formuliert. Die mitgelieferten Vorlagen sind ein Anfang, kein Endzustand:
Passen Sie sie an Ihre Fachsprache an. Eine Kanzlei will „Anliegen,
Sachverhalt, Mandant, Fristen", ein Vertrieb will etwas anderes.

„Auf Standard zurücksetzen" bringt die Werksfassung zurück.

### 3.5 Sprecher-Katalog (optional)

Wenn Sie einer Stimme im Transkript einen Namen geben, merkt sich Insilo
die Stimmcharakteristik. Beim nächsten Mal steht der Name von selbst da.
Die Stimmdaten bleiben auf der Box.

Sie können den Katalog auch vorab füllen und je Person eine Stimmprobe
von etwa 40 Sekunden aufnehmen.

---

## 4. Der tägliche Weg

### Aufnehmen

**Aufnahme** in der Navigation, Vorlage und Aufnahmesprache wählen, auf
das Mikrofon tippen. Insilo fragt beim ersten Mal die Mikrofon-Freigabe
des Browsers ab.

„Stopp & speichern" beendet die Aufnahme. Danach läuft im Hintergrund:
Transkription → Sprechertrennung → Zusammenfassung. Die Ansicht
aktualisiert sich selbst, Sie müssen nicht warten.

Insilo ist eine PWA — auf dem Telefon können Sie sie über „Zum
Startbildschirm hinzufügen" wie eine App ablegen.

### Ansehen und nacharbeiten

Auf der Besprechungsseite stehen Tonaufnahme, Transkript und
Zusammenfassung untereinander.

- **Sprecher zuweisen** — einen Abschnitt antippen und den Namen wählen.
  Das wirkt auf alle Abschnitte derselben Stimme.
- **Titel ändern** — direkt in der Überschrift.
- **Etiketten** — für Mandate, Fristsachen, Dezernate. Die
  Besprechungsliste filtert danach.
- **Erneut zusammenfassen** — nach einer Änderung an der Vorlage oder
  wenn der erste Lauf nichts hergab.

### Das Archiv befragen

**Archiv** beantwortet Fragen über alle Besprechungen hinweg und nennt
die Stellen, auf die sich die Antwort stützt („Welche Wiedervorlagen sind
in den nächsten zwei Wochen fällig?"). Dafür wird das Sprachmodell
befragt — steht es außerhalb der Box, gehen die gefundenen Ausschnitte
dorthin. Der Suchindex selbst bleibt hier.

### Schnellnotiz

**Idee** ist die Ein-Knopf-Aufnahme für unterwegs: tippen, sprechen,
fertig. Insilo strukturiert die Notiz und — anders als bei einer normalen
Aufnahme — **schickt sie ohne weitere Rückfrage an alle eingerichteten
Webhooks**. Das ist so gewollt (nach „Stopp" soll nichts mehr zu klicken
sein), aber Sie sollten es wissen, bevor Sie Webhooks einrichten.

---

## 5. Löschen, Papierkorb, Fristen

Löschen entfernt nichts sofort. Die Besprechung wandert in den
**Papierkorb** (Verweis oben rechts in der Besprechungsliste), samt
Tonaufnahme, und lässt sich bis zum Fristende zurückholen.

Es laufen **zwei Fristen nebeneinander**, und sie bedeuten Verschiedenes:

| Frist | Vorgabe | Was sie tut |
|---|---|---|
| Papierkorb-Frist | 30 Tage | entfernt die gelöschte Besprechung **ganz** |
| Aufbewahrungsfrist | 90 Tage | entfernt nur die **Tonaufnahme**, ab Aufnahmedatum |

Deshalb kann ein Eintrag im Papierkorb stehen und schon keine Aufnahme
mehr haben — dann steht es dort auch dran. Transkript und Zusammenfassung
bleiben in diesem Fall erhalten; sie brauchen einen Bruchteil des
Platzes.

Ein Aufräumlauf setzt beide Fristen jede Nacht um 3:30 Uhr durch
(Zeitzone des Containers; ohne gesetzte `TZ` ist das UTC). „Endgültig
löschen" im Papierkorb geht auch sofort — danach sind Tonaufnahme,
Transkript und Zusammenfassung weg, ohne Weg zurück.

### Fristen ändern

Beide Werte stehen in der Datenbank an der Organisation und haben
**noch keine Oberfläche**. Wer sie ändern will, braucht Zugriff auf die
Box-Datenbank:

```bash
kubectl exec -n os-platform citus-0 -- \
  psql -U olares -d <db-name> -c \
  "update public.orgs set trash_retention_days = 14, audio_retention_days = 30;"
```

Den Datenbanknamen liefert `DB_NAME` im Backend-Deployment.

> **Die Null bedeutet bei den beiden Werten Verschiedenes.** Bei der
> Aufbewahrungsfrist heißt `audio_retention_days = 0` **unbegrenzt** —
> die Aufnahmen bleiben liegen. Bei der Papierkorb-Frist heißt
> `trash_retention_days = 0` **keine Frist**: Gelöschtes ist beim
> nächsten nächtlichen Lauf endgültig weg. Der Papierkorb sagt das dann
> auch an: „Keine Frist gesetzt".

---

## 6. Was für die Datenschutzprüfung bereitsteht

Zwei Ansichten, die zusammen die zwei Fragen beantworten, die eine
Datenschutzbeauftragte stellt.

### „Was verlässt diese Box?"

Unten in der Navigation, immer sichtbar. Zeigt jedes eingerichtete Ziel
einzeln, mit **gemessener** Menge — nicht mit einer Zusicherung. Ist
nichts eingetragen, steht das da; ist ein fremder Endpunkt eingetragen,
steht sein Name da und wie viel dorthin ging.

Die Anzeige ist bewusst nicht pauschal „0 Byte": sobald ein externes
Sprachmodell oder ein Webhook eingerichtet ist, wäre das falsch.

### „Wer hat das veranlasst?"

**Protokoll** (Verweis unter dem Nachweis). Jede Änderung und jede
Ausleitung mit Urheber, Zeitpunkt und Gegenstand. Vorgänge, bei denen
Inhalte die Box verlassen können, sind als **Ausleitung** gekennzeichnet
und lassen sich einzeln filtern.

- Sie sehen Ihre eigenen Vorgänge.
- Inhaberinnen und Verwaltende der Organisation sehen alle.
- Einträge lassen sich **nicht ändern und nicht löschen** — das ist in
  der Datenbank festgelegt, nicht nur in der Anwendung.

**Was bewusst nicht darin steht:** der Wortlaut von Suchanfragen. Dass
jemand das Archiv befragt hat, gehört ins Protokoll; wonach er gefragt
hat, wäre Gesprächsinhalt.

### Trennung zwischen Organisationen

Jede Zeile in der Datenbank gehört einer Organisation, und die Datenbank
selbst setzt das durch — nicht die Anwendung. Eine Abfrage ohne
Nutzerkontext liefert **null Zeilen** statt aller. Wer die Anwendung
umgeht und direkt am Backend anklopft, kommt ohne den internen Schlüssel
nicht vorbei, auch nicht mit einem behaupteten Benutzernamen.

---

## 7. Anschluss an andere Systeme

Beides ist optional. Ohne diese Einrichtung geht nichts hinaus.

### Webhooks — Insilo meldet sich

**Einstellungen → Webhooks.** Insilo schickt bei Statusänderungen einer
Besprechung eine signierte Nachricht (`POST`) an Ihre Adresse; die
Signatur steht im Kopf `X-Insilo-Signature` und ist ein HMAC-SHA256 über
den Rumpf mit dem Geheimnis, das beim Anlegen erzeugt wird. Prüfen Sie
sie auf Ihrer Seite — sonst kann jeder diese Nachrichten stellen.

Bei `meeting.ready` liegt die vollständige Besprechung als Markdown bei.
Für dieses Ereignis gibt es zwei Betriebsarten:

- **manuell** — Insilo schickt erst, wenn jemand auf der Besprechung „An
  externe Systeme senden" drückt;
- **automatisch** — nach jeder fertigen Aufnahme.

Die Ausnahme steht in Abschnitt 4: eine **Schnellnotiz** geht immer
automatisch hinaus, auch an Webhooks in Betriebsart „manuell".

### Zugriffsschlüssel — andere Systeme holen ab

**Einstellungen → API-Schlüssel.** Ein Schlüssel erlaubt einem externen
System, Besprechungen **lesend** abzurufen:

```
GET /api/external/v1/meetings
GET /api/external/v1/meetings/<id>
GET /api/external/v1/meetings/<id>/markdown
Authorization: Bearer inskey_…
```

Der Schlüssel wird **einmal** angezeigt und danach nie wieder — Insilo
speichert nur einen Hash davon. Jeder Schlüssel gilt für genau Ihre
Organisation. Jeder Abruf über einen Schlüssel steht als Ausleitung im
Protokoll, mit dem Namen des Schlüssels als Urheber.

„Widerrufen" entzieht den Zugriff sofort.

---

## 8. Sichern und wiederherstellen

Eine Sicherung besteht aus **zwei Hälften**. Wer nur eine zieht, kann
nicht wiederherstellen.

| Hälfte | Was drin ist |
|---|---|
| Die Datenbank | Besprechungen, Transkripte, Zusammenfassungen, Etiketten, Protokoll, Einstellungen, Zugriffsschlüssel |
| `/app/data` | Die Tonaufnahmen **und** `konfiguration.json` — der Abzug der Einrichtung; er **enthält Zugangsdaten** und liegt mit Rechten 0600 |

Olares' eingebautes Velero sichert das Volume und ist von allem Folgenden
nicht betroffen — es arbeitet unterhalb der Datenbank. Empfohlen: täglich
inkrementell, wöchentlich voll, Ziel ist ein eigener NAS oder ein
verschlüsselter Speicher, den Sie kontrollieren.

### Der Datenbank-Abzug muss als Superuser laufen

```bash
kubectl exec -n os-platform citus-0 -- \
  pg_dump -U olares -d <db-name> --no-owner --no-acl > sicherung.sql
```

Unter der Kennung der Anwendung **bricht `pg_dump` ab**:

```
ERROR: query would be affected by row-level security policy for table "api_keys"
```

Das ist die richtige Reaktion, keine Störung — das Werkzeug verweigert
lieber den Dienst, als eine unvollständige Sicherung zu schreiben.
`olares` ist der Superuser der Box-Datenbank und sieht alles.

### Zurückspielen

```bash
psql -U olares -d <neue-db> -v ON_ERROR_STOP=1 -f sicherung.sql
```

Am 6.9.2026 einmal wirklich durchgespielt, gegen eine Kopie: ohne einen
einzigen Fehler durchgelaufen, alle Tabellen deckungsgleich, die
Zeilensicherheit mitgewandert, kein Verweis auf eine fehlende Tondatei.

### Vorsicht bei der Deinstallation

Eine Deinstallation löscht die **Datenbank**. `/app/data` überlebt, aber
Olares legt die Datenbank neu an — samt neuer Kennung der Organisation.
Die vorhandenen Tonaufnahmen hingen danach in der Luft — sie liegen unter
`audio/<org-id>/`. Dagegen schreibt
Insilo den erwähnten Abzug der Einrichtung neben das Audio und liest ihn
beim Start zurück, wenn die Datenbank leer ist. Verlassen Sie sich
trotzdem nicht darauf: **vor jedem Eingriff eine Sicherung.**

---

## 9. Aktualisieren

Steht Insilo im Markt, meldet die Box „Update verfügbar". Sie entscheiden
wann — es gibt **keine** automatischen Aktualisierungen ohne Ihre
Zustimmung.

Olares tauscht die Container nacheinander aus und nimmt bei einem
Fehlschlag die alte Fassung zurück. Ihre Daten bleiben, wo sie sind.

Bei einer gelieferten `.tgz`-Datei ist der Weg derselbe wie bei der
Installation (**Upload custom chart**).

---

## 10. Wenn etwas nicht geht

**„Unknown identity. Ask an administrator to add this user."**
Dieser Olares-Benutzername steht noch nicht in der Datenbank. Insilo legt
niemanden mehr von selbst an — eintragen wie in Abschnitt 2 beschrieben.

**„Zusammenfassungen sind aus, bis das Sprachmodell eingerichtet ist."**
Erwartet, solange unter Einstellungen keine Adresse steht. Abschnitt 3.1.
Aufnahme und Transkription laufen davon unabhängig weiter.

**Die Aufnahme läuft, das Transkript kommt nicht.** Wenn Sie eine externe
Spracherkennung eingetragen haben: fehlt die Modell-ID, lehnt der
Endpunkt jede Anfrage ab. Welche Kennungen er kennt, steht bei ihm unter
`/v1/models`.

**„Mikrofonzugriff verweigert".** Eine Einstellung des Browsers, nicht
von Insilo. Im Schloss-Symbol der Adresszeile die Freigabe für die
Insilo-Adresse erteilen.

**„Browser unterstützt keine Aufnahme".** Ein aktueller Chrome oder
Safari nimmt auf. Ältere Browser und einige eingebettete Ansichten nicht.

**Die Besprechung steht auf „Fehlgeschlagen".** „Erneut zusammenfassen"
auf der Besprechungsseite stößt den Lauf neu an. Bleibt es dabei, ist
meist das Sprachmodell nicht erreichbar — der Test unter Einstellungen
sagt es Ihnen.

**Eine Besprechung ist versehentlich gelöscht.** Papierkorb, „Zurückholen"
— bis die Frist abläuft (Abschnitt 5).

**Nichts davon passt.** Der Support von kaivo.studio braucht: was Sie
getan haben, was dastand, und den Zeitpunkt — damit lässt sich die Zeile
im Protokoll finden.

---

## 11. Was Insilo nicht tut

- **Keine Telemetrie, kein Nach-Hause-Melden.** Auch keine anonyme
  Nutzungsstatistik.
- **Kein Abgleich zwischen Boxen.** Das würde das Versprechen brechen,
  auf dem das Ganze steht.
- **Keine automatische Aktualisierung** ohne Ihre Zustimmung.
- **Keine eigene Anmeldung.** Die macht Olares; Insilo baut keine zweite
  Benutzerverwaltung daneben.
- **Kein Rückgriff auf eine Cloud-KI, wenn das lokale Modell schweigt.**
  Dann fehlt die Zusammenfassung, und Insilo sagt das — statt still
  woanders zu fragen.
- **Keine Schriften von fremden Servern.** Auch nicht beim Bauen.

---

*Insilo — kaivo.studio. Vertrieb über aimighty.de.*
