-- ========================================================================
-- seed.sql — System-Templates (v0.1.40 Prompt-Iteration)
--
-- Zielsystem: Qwen 2.5 14B Instruct Q4_K_M über Olares-LiteLLM (oder
-- jeder OpenAI-kompatible Endpoint). Prompts folgen einheitlicher
-- Markdown-Struktur (## Aufgabe / Eingabeformat / Regeln / Ausgabe),
-- Imperativ ohne Anrede, expliziter Hallu-Schutz, `[Sprecher]:`-Format-
-- Hint. Jedes Schema hat ein führendes `_analyse`-Feld für CoT-vor-JSON.
--
-- ON CONFLICT DO UPDATE: idempotent — jeder Init-Container-Run schreibt
-- die neuesten Defaults. User-Overrides leben in template_customizations
-- und werden NICHT überschrieben.
-- ========================================================================

insert into public.templates (
  id, org_id, name, description, category,
  system_prompt, output_schema, few_shot_input, few_shot_output,
  is_system, is_active, version
)
values
-- ============================================================
-- 1) Allgemeine Besprechung
-- ============================================================
(
  '00000000-0000-0000-0000-000000000001',
  null,
  'Allgemeine Besprechung',
  'Standard-Zusammenfassung für interne und externe Meetings.',
  'general',
  $prompt$## Aufgabe
Erstelle ein strukturiertes Protokoll des folgenden Geschäftsmeetings.

## Eingabeformat
Das Transkript zeigt jeden Sprecherbeitrag als `[Sprecher]: Text`. Die Namen sind verlässlich — attributiere Aussagen, Beschlüsse und Aufgaben den jeweiligen Personen.

## Regeln
- Verwende ausschließlich Informationen aus dem Transkript.
- Wenn eine Information nicht im Transkript steht, lass das Feld leer oder setze es auf `null` — erfinde nichts.
- Schreibe in formellem Deutsch, sachlich und prägnant. Keine Marketing-Floskeln, keine Superlative.
- Bei Beschlüssen mit Verantwortlichkeit und Frist: nur eintragen, was wörtlich vereinbart wurde.

## Ausgabe
Gib ausschließlich ein JSON-Objekt nach dem definierten Schema zurück. Beginne mit dem Feld `_analyse` (2-3 Sätze zu Schwerpunkt und Feldabdeckung), arbeite dann die Hauptfelder ab.$prompt$,
  $schema${
    "type": "object",
    "properties": {
      "_analyse": {
        "type": "string",
        "description": "2-3 Sätze: Worauf liegt der Fokus dieses Meetings? Welche Felder werden gefüllt, welche bleiben leer und warum?"
      },
      "anwesende": { "type": "array", "items": { "type": "string" } },
      "kernthemen": { "type": "array", "items": { "type": "string" } },
      "wichtige_aussagen": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "sprecher": { "type": "string" },
            "aussage": { "type": "string" }
          }
        }
      },
      "beschluesse": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "beschluss": { "type": "string" },
            "verantwortlich": { "type": "string" },
            "frist": { "type": "string" }
          }
        }
      },
      "offene_fragen": { "type": "array", "items": { "type": "string" } },
      "naechste_schritte": { "type": "array", "items": { "type": "string" } }
    },
    "required": ["_analyse", "kernthemen", "beschluesse", "naechste_schritte"]
  }$schema$::jsonb,
  $few$[Kai Böhm]: Wir müssen heute klären, wie wir mit dem neuen Hosting-Setup umgehen. Lea, du hattest dir die Angebote angeschaut.
[Lea Schmidt]: Ja. Hetzner und IONOS sind beide ähnlich teuer, aber Hetzner hat den besseren Support. Ich würde Hetzner nehmen.
[Kai Böhm]: Einverstanden. Lea, kannst du den Vertrag bis Ende der Woche aufsetzen?
[Lea Schmidt]: Bis Freitag, ja.
[Kai Böhm]: Gut. Marc, du kümmerst dich um die Migration der bestehenden Daten — Zeitrahmen offen, aber spätestens Ende des Monats.
[Marc Berger]: Mach ich. Ich brauche dafür noch Zugriff aufs alte System.
[Kai Böhm]: Den besorge ich dir bis Montag. Sonst noch offene Punkte?
[Lea Schmidt]: Wir haben das DSGVO-Thema noch nicht angeschnitten — das müssen wir vor der Migration klären.$few$,
  $few${
    "_analyse": "Kurzes Entscheidungs-Meeting zum Hosting-Wechsel. Anwesende (Kai, Lea, Marc) klar identifiziert. Zwei konkrete Beschlüsse mit Verantwortlichen und Fristen. Eine offene Frage zur DSGVO blockiert die Migration.",
    "anwesende": ["Kai Böhm", "Lea Schmidt", "Marc Berger"],
    "kernthemen": [
      "Auswahl des Hosting-Anbieters",
      "Zeitplan für die Migration der Bestandsdaten",
      "DSGVO-Konformität vor Migration"
    ],
    "wichtige_aussagen": [
      {"sprecher": "Lea Schmidt", "aussage": "Hetzner und IONOS sind preislich ähnlich; Hetzner hat den besseren Support."}
    ],
    "beschluesse": [
      {"beschluss": "Hetzner wird als neuer Hosting-Anbieter gewählt.", "verantwortlich": "Lea Schmidt", "frist": "Vertrag bis Freitag"},
      {"beschluss": "Migration der Bestandsdaten ins neue Hosting.", "verantwortlich": "Marc Berger", "frist": "Ende des Monats"},
      {"beschluss": "Zugriff aufs alte System für Marc Berger einrichten.", "verantwortlich": "Kai Böhm", "frist": "Montag"}
    ],
    "offene_fragen": [
      "DSGVO-Konformität muss vor der Migration final geklärt werden."
    ],
    "naechste_schritte": [
      "Lea setzt den Hetzner-Vertrag bis Freitag auf.",
      "Kai stellt Marc bis Montag Zugriff aufs alte System bereit.",
      "DSGVO-Thema vor Migrationsbeginn klären."
    ]
  }$few$::jsonb,
  true,
  true,
  2
),

-- ============================================================
-- 2) Mandantengespräch (anwaltlich / steuerlich)
-- ============================================================
(
  '00000000-0000-0000-0000-000000000002',
  null,
  'Mandantengespräch',
  'Strukturiertes Aktenprotokoll für anwaltliche und steuerliche Mandantengespräche.',
  'legal',
  $prompt$## Aufgabe
Erstelle ein Aktenprotokoll des folgenden Mandantengesprächs.

## Eingabeformat
Das Transkript zeigt jeden Sprecherbeitrag als `[Sprecher]: Text`. Trenne klar zwischen Mandantenangaben (Sachverhalt aus erster Hand) und den Einordnungen der Beraterin/des Beraters.

## Regeln
- Strikt wahren: anwaltliche/steuerliche Schweigepflicht. Keine wertenden Adjektive über Mandanten oder Dritte.
- Keine eigenen rechtlichen Wertungen, keine Empfehlungen, kein Mandatsgeheimnis-Sprung. Nur dokumentieren, was im Gespräch gesagt wurde.
- Bei Beträgen, Daten, Fristen und Aktenzeichen: exakte wörtliche Wiedergabe. Keine Annäherungen.
- Wenn eine Angabe nicht im Transkript steht (z. B. Honorar wurde nicht thematisiert), lass das Feld leer oder setze es auf `null` — erfinde nichts.
- Schreibe in formellem Deutsch.

## Ausgabe
Gib ausschließlich ein JSON-Objekt nach dem definierten Schema zurück. Beginne mit dem Feld `_analyse` (2-3 Sätze zum Gesprächsschwerpunkt und welche Felder mangels Datenlage leer bleiben), arbeite dann die Hauptfelder ab.$prompt$,
  $schema${
    "type": "object",
    "properties": {
      "_analyse": {
        "type": "string",
        "description": "2-3 Sätze: Worum geht es im Mandat? Welche Felder werden mangels Datenlage leer bleiben?"
      },
      "mandantenname": { "type": "string" },
      "sachverhalt": { "type": "string" },
      "rechtsfragen": { "type": "array", "items": { "type": "string" } },
      "eingebrachte_unterlagen": { "type": "array", "items": { "type": "string" } },
      "vereinbarte_leistungen": { "type": "array", "items": { "type": "string" } },
      "wichtige_termine_fristen": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "termin": { "type": "string" },
            "frist": { "type": "string" }
          }
        }
      },
      "honorarvereinbarung": { "type": "string" },
      "naechste_schritte_mandat": { "type": "array", "items": { "type": "string" } }
    },
    "required": ["_analyse", "sachverhalt", "vereinbarte_leistungen", "naechste_schritte_mandat"]
  }$schema$::jsonb,
  $few$[Dr. Wagner]: Frau Müller, schildern Sie mir bitte den Sachverhalt.
[Frau Müller]: Mein Arbeitgeber hat mir letzte Woche mündlich gekündigt, ohne schriftliche Bestätigung. Ich arbeite seit zwölf Jahren in der Firma.
[Dr. Wagner]: Lag eine Abmahnung vor?
[Frau Müller]: Nein, gar keine. Ich habe auch keine Probleme mit Kollegen. Ich habe den Arbeitsvertrag und meine letzte Lohnabrechnung mitgebracht.
[Dr. Wagner]: Sehr gut. Wir prüfen die Wirksamkeit der Kündigung. Die Klagefrist beträgt drei Wochen ab schriftlichem Zugang — wann genau wurde Ihnen gekündigt?
[Frau Müller]: Am 8. Mai mündlich, schriftlich habe ich bis heute nichts.
[Dr. Wagner]: Wir werden Kündigungsschutzklage einreichen, sobald der schriftliche Bescheid vorliegt. Vereinbaren wir mein Honorar nach RVG. Senden Sie mir bitte sofort eine Kopie der schriftlichen Kündigung, wenn diese kommt.
[Frau Müller]: Mache ich. Wie geht es jetzt weiter?
[Dr. Wagner]: Ich nehme schriftlich Kontakt mit dem Arbeitgeber auf und fordere die schriftliche Kündigung an. Wiedervorlage in einer Woche.$few$,
  $few${
    "_analyse": "Mandantin schildert mündliche Kündigung ohne Abmahnung nach 12 Jahren Betriebszugehörigkeit. Klagefristen abhängig vom schriftlichen Zugang — der noch aussteht. Honorar nach RVG vereinbart, Wiedervorlage in einer Woche.",
    "mandantenname": "Frau Müller",
    "sachverhalt": "Mandantin wurde am 8. Mai mündlich von ihrem Arbeitgeber gekündigt. Die Mandantin ist seit zwölf Jahren in der Firma beschäftigt. Eine Abmahnung liegt nach Aussage der Mandantin nicht vor. Eine schriftliche Kündigung ist bislang nicht zugegangen.",
    "rechtsfragen": [
      "Wirksamkeit der mündlich ausgesprochenen Kündigung",
      "Beginn der dreiwöchigen Klagefrist (§ 4 KSchG) bei mündlicher Kündigung",
      "Mögliche Kündigungsschutzklage"
    ],
    "eingebrachte_unterlagen": [
      "Arbeitsvertrag",
      "Letzte Lohnabrechnung"
    ],
    "vereinbarte_leistungen": [
      "Prüfung der Wirksamkeit der mündlichen Kündigung",
      "Schriftliche Aufforderung an den Arbeitgeber zur Vorlage einer schriftlichen Kündigung",
      "Vorbereitung einer Kündigungsschutzklage nach Zugang der schriftlichen Kündigung"
    ],
    "wichtige_termine_fristen": [
      {"termin": "Wiedervorlage", "frist": "Eine Woche nach Erstgespräch"},
      {"termin": "Klagefrist nach KSchG", "frist": "Drei Wochen ab schriftlichem Zugang der Kündigung"}
    ],
    "honorarvereinbarung": "Abrechnung nach RVG (Rechtsanwaltsvergütungsgesetz)",
    "naechste_schritte_mandat": [
      "Mandantin sendet Kopie der schriftlichen Kündigung sofort nach Zugang.",
      "Kanzlei nimmt schriftlich Kontakt mit dem Arbeitgeber auf.",
      "Wiedervorlage in einer Woche."
    ]
  }$few$::jsonb,
  true,
  true,
  2
),

-- ============================================================
-- 3) Vertriebsgespräch (BANT-Stil)
-- ============================================================
(
  '00000000-0000-0000-0000-000000000003',
  null,
  'Vertriebsgespräch',
  'Discovery Call oder Kundentermin im Vertrieb, ausgewertet im BANT-Schema.',
  'sales',
  $prompt$## Aufgabe
Werte das folgende Vertriebsgespräch nach dem BANT-Schema aus.

## Eingabeformat
Das Transkript zeigt jeden Sprecherbeitrag als `[Sprecher]: Text`. Identifiziere klar, wer auf Kunden- und wer auf Vertriebsseite spricht, und attribuiere Aussagen entsprechend.

## Regeln
- Strikt nüchtern: keine vertriebliche Übertreibung, keine Wunschdenken-Interpretationen.
- BANT-Felder: nur ausfüllen, wenn das Transkript konkrete Angaben liefert. Wurde ein Punkt nicht erfragt oder beantwortet, schreibe wörtlich „nicht erfragt" — nicht raten.
- `verkaufschance_einschaetzung`: nur einer der vier Enum-Werte ist erlaubt. Stütze die Wahl auf konkrete Signale aus dem Transkript (zitierbar).
- Einwände wörtlich oder eng paraphrasiert wiedergeben.
- Wenn eine Information fehlt: leer oder `null` — nicht erfinden.
- Schreibe in formellem Deutsch.

## Ausgabe
Gib ausschließlich ein JSON-Objekt nach dem definierten Schema zurück. Beginne mit dem Feld `_analyse` (2-3 Sätze zum Gesprächsverlauf und worauf die Einschätzung fußt), arbeite dann die Hauptfelder ab.$prompt$,
  $schema${
    "type": "object",
    "properties": {
      "_analyse": {
        "type": "string",
        "description": "2-3 Sätze: Wie verlief das Gespräch, worauf stützt sich die Verkaufschance-Einschätzung, welche BANT-Felder fehlen?"
      },
      "kunde": { "type": "string" },
      "schmerzpunkte": { "type": "array", "items": { "type": "string" } },
      "aktuelle_loesung": { "type": "string" },
      "bant": {
        "type": "object",
        "properties": {
          "budget": { "type": "string" },
          "entscheider": { "type": "string" },
          "need": { "type": "string" },
          "timing": { "type": "string" }
        }
      },
      "einwaende": { "type": "array", "items": { "type": "string" } },
      "vereinbarte_naechste_schritte": { "type": "array", "items": { "type": "string" } },
      "follow_up_datum": { "type": "string" },
      "verkaufschance_einschaetzung": {
        "type": "string",
        "enum": ["hoch", "mittel", "niedrig", "unklar"]
      }
    },
    "required": ["_analyse", "schmerzpunkte", "vereinbarte_naechste_schritte"]
  }$schema$::jsonb,
  $few$[Markus (Vertrieb)]: Vielen Dank für die Zeit, Frau Schäfer. Welche Themen treiben Sie aktuell um?
[Frau Schäfer]: Wir wachsen schneller als geplant — 40 % mehr Mitarbeiter dieses Jahr. Unser HR-Tool kommt nicht mit. Wir verlieren Tage mit Workarounds in Excel.
[Markus (Vertrieb)]: Verstehe. Wer entscheidet bei Ihnen typischerweise über solche Tools?
[Frau Schäfer]: Ich gemeinsam mit unserem CFO. Budget liegt im Q3 frei, etwa 30.000 € jährlich.
[Markus (Vertrieb)]: Wann müsste die neue Lösung produktiv sein?
[Frau Schäfer]: Spätestens Ende Q4 — danach kommt unser nächster Hiring-Sprint. Aber ehrlich gesagt: wir hatten in der Vergangenheit Probleme mit DSGVO-Konformität bei Cloud-Tools. Das ist der Knackpunkt.
[Markus (Vertrieb)]: Verständlich. Wir bringen Ihnen unsere DSGVO-Dokumentation ins nächste Meeting mit. Wann passt es?
[Frau Schäfer]: Donnerstag in zwei Wochen, 14 Uhr.
[Markus (Vertrieb)]: Setze ich auf. Senden Sie mir bis dahin Ihre aktuelle Mitarbeiterzahl und die geplante Wachstumskurve?$few$,
  $few${
    "_analyse": "Discovery-Call mit Frau Schäfer (HR-Leitung). Wachstumsschmerz akut, BANT größtenteils befüllt, Hauptblocker DSGVO-Compliance. Folgetermin in zwei Wochen mit konkretem Lieferziel. Einschätzung mittel — Bedarf und Timing klar, aber DSGVO-Einwand muss adressiert werden.",
    "kunde": "Frau Schäfer (HR-Leitung)",
    "schmerzpunkte": [
      "40 % Mitarbeiterwachstum innerhalb eines Jahres",
      "Bestehendes HR-Tool skaliert nicht mit",
      "Tägliche Workarounds in Excel"
    ],
    "aktuelle_loesung": "Bestehendes HR-Tool ergänzt durch manuelle Excel-Workarounds",
    "bant": {
      "budget": "Etwa 30.000 € jährlich, im Q3 freigegeben",
      "entscheider": "Frau Schäfer gemeinsam mit dem CFO",
      "need": "Skalierbares HR-Tool für 40 %-Wachstum, DSGVO-konform",
      "timing": "Produktivsetzung spätestens Ende Q4 vor nächstem Hiring-Sprint"
    },
    "einwaende": [
      "DSGVO-Konformität bei Cloud-Tools — frühere Probleme als Hauptknackpunkt"
    ],
    "vereinbarte_naechste_schritte": [
      "Folgetermin Donnerstag in zwei Wochen, 14 Uhr.",
      "Vertrieb bringt DSGVO-Dokumentation zum Folgetermin mit.",
      "Frau Schäfer sendet aktuelle Mitarbeiterzahl und geplante Wachstumskurve vor dem Termin."
    ],
    "follow_up_datum": "Donnerstag in zwei Wochen, 14 Uhr",
    "verkaufschance_einschaetzung": "mittel"
  }$few$::jsonb,
  true,
  true,
  2
),

-- ============================================================
-- 4) Jahresgespräch (Bestandskundenpflege)
-- ============================================================
(
  '00000000-0000-0000-0000-000000000004',
  null,
  'Jahresgespräch',
  'Strukturiertes Protokoll für jährliche Kunden- oder Bestandsgespräche.',
  'consulting',
  $prompt$## Aufgabe
Erstelle ein Protokoll des folgenden Jahresgesprächs für die Kundenakte.

## Eingabeformat
Das Transkript zeigt jeden Sprecherbeitrag als `[Sprecher]: Text`. Die Namen sind verlässlich — attributiere Aussagen, Beschlüsse und Wünsche den richtigen Personen.

## Regeln
- Risikoveränderungen seit dem Vorjahr klar herausarbeiten: gestiegen, gesunken, neu, weggefallen.
- Cross-Selling-Potenziale notieren, ohne aufdringlich oder verkäuferisch zu wirken — neutrale Beobachtung.
- Wiedervorlage-Datum sinnvoll setzen (typisch: nächstes Jahresgespräch in 12 Monaten, früher wenn das Transkript es nahelegt).
- Wenn eine Information nicht im Transkript steht, lass das Feld leer oder setze es auf `null` — nicht erfinden.
- Schreibe in formellem Deutsch.

## Ausgabe
Gib ausschließlich ein JSON-Objekt nach dem definierten Schema zurück. Beginne mit dem Feld `_analyse` (2-3 Sätze zum Gesundheitszustand der Kundenbeziehung), arbeite dann die Hauptfelder ab.$prompt$,
  $schema${
    "type": "object",
    "properties": {
      "_analyse": {
        "type": "string",
        "description": "2-3 Sätze: Wie steht die Kundenbeziehung? Welche Veränderungen vs. Vorjahr sind wesentlich?"
      },
      "kunde": { "type": "string" },
      "anwesende": { "type": "array", "items": { "type": "string" } },
      "bestandsuebersicht": { "type": "array", "items": { "type": "string" } },
      "risikoveraenderungen": { "type": "array", "items": { "type": "string" } },
      "cross_selling_potenziale": { "type": "array", "items": { "type": "string" } },
      "kundenwuensche": { "type": "array", "items": { "type": "string" } },
      "beschluesse": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "beschluss": { "type": "string" },
            "verantwortlich": { "type": "string" },
            "frist": { "type": "string" }
          }
        }
      },
      "wiedervorlage": { "type": "string" }
    },
    "required": ["_analyse", "bestandsuebersicht", "beschluesse", "wiedervorlage"]
  }$schema$::jsonb,
  $few$[Berater Klein]: Herr Vogel, schön Sie zu sehen. Wir blicken aufs letzte Jahr zurück — was hat sich bei Ihnen verändert?
[Herr Vogel]: Wir haben den dritten Standort eröffnet, in Hamburg. Damit sind wir jetzt auf 85 Mitarbeiter. Außerdem haben wir die GmbH in eine GmbH & Co. KG umgewandelt.
[Berater Klein]: Das ändert einiges in Ihrer Steuerstruktur. Wie läuft die Berufshaftpflicht aktuell?
[Herr Vogel]: Die ist solide, aber wir brauchen eine Anpassung wegen des neuen Standorts. Mit der D&O-Versicherung möchte ich auch nochmal sprechen — der Vorstand ist gewachsen.
[Berater Klein]: Notiere ich. Und wie steht's mit Ihrer Altersvorsorge? Hatten wir letztes Jahr angeschnitten.
[Herr Vogel]: Da ist nichts passiert, ehrlich gesagt. Schieben wir auf, ich muss erst mal die KG sauber zum Laufen kriegen.
[Berater Klein]: Verstehe. Ich notiere als Wiedervorlage für unser Gespräch in einem halben Jahr. Heute aktualisieren wir die Berufshaftpflicht und planen ein D&O-Gespräch in vier Wochen.
[Herr Vogel]: Passt. Frau Vogel würde gerne nächstes Jahr auch dabei sein, ich nehme sie mit ins Geschäft.$few$,
  $few${
    "_analyse": "Bestandskunde Herr Vogel: deutlich expandiert (3. Standort, GmbH→GmbH & Co. KG, +Mitarbeiter). Risikoprofil hat sich verändert, Berufshaftpflicht-Anpassung und D&O-Gespräch wurden vereinbart. Altersvorsorge bewusst verschoben — Wiedervorlage in 6 Monaten.",
    "kunde": "Herr Vogel",
    "anwesende": ["Berater Klein", "Herr Vogel"],
    "bestandsuebersicht": [
      "Berufshaftpflicht aktuell solide",
      "D&O-Versicherung bestehend, Vorstand inzwischen gewachsen",
      "Altersvorsorge weiterhin nicht aufgesetzt"
    ],
    "risikoveraenderungen": [
      "Dritter Standort eröffnet (Hamburg) — erhöht Berufshaftpflicht-Bedarf",
      "Umwandlung GmbH → GmbH & Co. KG — neue Steuerstruktur",
      "Mitarbeiterzahl auf 85 gewachsen",
      "Vorstand vergrößert — D&O-Anpassungsbedarf"
    ],
    "cross_selling_potenziale": [
      "Altersvorsorge weiterhin offen (vom Kunden bewusst verschoben)",
      "Nachfolgeplanung mit Frau Vogel (geplante Einbindung im nächsten Jahresgespräch)"
    ],
    "kundenwuensche": [
      "Berufshaftpflicht an den neuen Standort anpassen",
      "Gespräch zur D&O-Versicherung mit erweitertem Vorstand",
      "Frau Vogel beim nächsten Jahresgespräch einbinden"
    ],
    "beschluesse": [
      {"beschluss": "Berufshaftpflicht aktualisieren wegen 3. Standort", "verantwortlich": "Berater Klein", "frist": "Heute / unmittelbar nach Termin"},
      {"beschluss": "D&O-Gespräch ansetzen", "verantwortlich": "Berater Klein", "frist": "In vier Wochen"}
    ],
    "wiedervorlage": "In 6 Monaten (Halbjahres-Update zu KG-Setup und Altersvorsorge)"
  }$few$::jsonb,
  true,
  true,
  2
)
on conflict (id) do update set
  name             = excluded.name,
  description      = excluded.description,
  category         = excluded.category,
  system_prompt    = excluded.system_prompt,
  output_schema    = excluded.output_schema,
  few_shot_input   = excluded.few_shot_input,
  few_shot_output  = excluded.few_shot_output,
  is_system        = excluded.is_system,
  is_active        = excluded.is_active,
  version          = excluded.version,
  updated_at       = now();
