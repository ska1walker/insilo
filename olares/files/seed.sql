-- ========================================================================
-- seed.sql - System-Templates für die Erst-Inbetriebnahme
-- ========================================================================

insert into public.templates (id, org_id, name, description, category, system_prompt, output_schema, is_system, is_active)
values
-- ============================================================
-- Allgemeine Besprechung
-- ============================================================
(
  '00000000-0000-0000-0000-000000000001',
  null,
  'Allgemeine Besprechung',
  'Standard-Zusammenfassung für interne und externe Meetings.',
  'general',
  'Du bist ein professioneller Protokollführer für deutsche Geschäftsmeetings. Analysiere das folgende Meeting-Transkript und erstelle eine strukturierte Zusammenfassung.

Wichtige Regeln:
- Schreibe in formellem Deutsch.
- Halte dich strikt an die im Transkript genannten Fakten.
- Nenne Personen mit ihren Speaker-Labels.
- Sei präzise und prägnant, vermeide Floskeln.
- Wenn ein Aspekt im Meeting nicht behandelt wurde, lass das entsprechende Feld leer.',
  '{
    "type": "object",
    "properties": {
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
    "required": ["kernthemen", "beschluesse", "naechste_schritte"]
  }'::jsonb,
  true,
  true
),
-- ============================================================
-- Mandantengespräch
-- ============================================================
(
  '00000000-0000-0000-0000-000000000002',
  null,
  'Mandantengespräch',
  'Strukturiertes Protokoll für anwaltliche und steuerliche Mandantengespräche.',
  'legal',
  'Du bist ein erfahrener Protokollführer für anwaltliche und steuerliche Mandantengespräche. Analysiere das folgende Transkript und erstelle ein strukturiertes Aktenprotokoll.

Wichtige Regeln:
- Wahrung der anwaltlichen/steuerlichen Schweigepflicht in jeder Formulierung.
- Sachverhalt strikt nach Transkript, keine eigenen rechtlichen Wertungen.
- Identifiziere klar: was hat der Mandant geschildert, was hat der Berater eingeordnet.
- Bei Beträgen, Daten und Fristen: exakte Wiedergabe.',
  '{
    "type": "object",
    "properties": {
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
    "required": ["sachverhalt", "vereinbarte_leistungen", "naechste_schritte_mandat"]
  }'::jsonb,
  true,
  true
),
-- ============================================================
-- Vertriebsgespräch
-- ============================================================
(
  '00000000-0000-0000-0000-000000000003',
  null,
  'Vertriebsgespräch',
  'Discovery Call oder Kundentermin im Vertrieb.',
  'sales',
  'Du bist ein erfahrener Vertriebsanalyst. Analysiere das folgende Vertriebsgespräch und erstelle eine strukturierte Auswertung im BANT-Stil.

Regeln:
- Sachlich und nüchtern, keine vertriebliche Übertreibung.
- Wenn Informationen fehlen, dies explizit notieren ("nicht erfragt").
- Sprecher klar als Kunde vs. Vertrieb identifizieren.',
  '{
    "type": "object",
    "properties": {
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
    "required": ["schmerzpunkte", "vereinbarte_naechste_schritte"]
  }'::jsonb,
  true,
  true
),
-- ============================================================
-- Jahresgespräch
-- ============================================================
(
  '00000000-0000-0000-0000-000000000004',
  null,
  'Jahresgespräch',
  'Strukturiertes Protokoll für jährliche Kunden- oder Bestandsgespräche.',
  'consulting',
  'Du bist ein erfahrener Berater. Analysiere das folgende Jahresgespräch und erstelle ein strukturiertes Protokoll für die Kundenakte.

Regeln:
- Formelles Deutsch.
- Risikoveränderungen seit dem Vorjahr klar herausarbeiten.
- Cross-Selling-Potenziale notieren ohne aufdringlich zu wirken.
- Wiedervorlage-Datum sinnvoll setzen.',
  '{
    "type": "object",
    "properties": {
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
    "required": ["bestandsuebersicht", "beschluesse", "wiedervorlage"]
  }'::jsonb,
  true,
  true
);
