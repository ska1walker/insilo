-- ========================================================================
-- seed.sql — System-Templates (v0.1.46 i18n Phase 3)
--
-- Zielsystem: Qwen 2.5 14B Instruct Q4_K_M über Olares-LiteLLM (oder
-- jeder OpenAI-kompatible Endpoint). Prompts folgen einheitlicher
-- Markdown-Struktur (## Aufgabe / Eingabeformat / Regeln / Ausgabe),
-- Imperativ ohne Anrede, expliziter Hallu-Schutz, `[Sprecher]:`-Format-
-- Hint. Jedes Schema hat ein führendes `_analyse`-Feld für CoT-vor-JSON.
--
-- v0.1.46+: `system_prompts JSONB` enthält Prompts pro UI-Locale
-- (`de`/`en`/`fr`/`es`/`it`). Die JSON-Schema-Feldnamen bleiben Deutsch
-- (z. B. `zusammenfassung`, `kernpunkte`) — übersetzt wird nur der
-- Inhalt, nicht das Schema.
--
-- v0.1.48: Legacy `system_prompt TEXT`-Slot in Migration 0013 entfernt.
-- Seed schreibt nur noch die JSONB-Map.
--
-- ON CONFLICT DO UPDATE: idempotent — jeder Init-Container-Run schreibt
-- die neuesten Defaults. User-Overrides leben in template_customizations
-- und werden NICHT überschrieben.
-- ========================================================================

insert into public.templates (
  id, org_id, name, description, category,
  system_prompts, output_schema, few_shot_input, few_shot_output,
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
  jsonb_build_object(
    'de', $de$## Aufgabe
Erstelle ein strukturiertes Protokoll des folgenden Geschäftsmeetings.

## Eingabeformat
Das Transkript zeigt jeden Sprecherbeitrag als `[Sprecher]: Text`. Die Namen sind verlässlich — attributiere Aussagen, Beschlüsse und Aufgaben den jeweiligen Personen.

## Regeln
- Verwende ausschließlich Informationen aus dem Transkript.
- Wenn eine Information nicht im Transkript steht, lass das Feld leer oder setze es auf `null` — erfinde nichts.
- Schreibe in formellem Deutsch, sachlich und prägnant. Keine Marketing-Floskeln, keine Superlative.
- Bei Beschlüssen mit Verantwortlichkeit und Frist: nur eintragen, was wörtlich vereinbart wurde.

## Ausgabe
Gib ausschließlich ein JSON-Objekt nach dem definierten Schema zurück. Beginne mit dem Feld `_analyse` (2-3 Sätze zu Schwerpunkt und Feldabdeckung), arbeite dann die Hauptfelder ab.$de$,
    'en', $en$## Task
Produce a structured minutes record of the following business meeting.

## Input format
The transcript shows each speaker turn as `[Speaker]: Text`. The names are reliable — attribute statements, decisions and tasks to the respective persons.

## Rules
- Use only information that appears in the transcript.
- If a piece of information is not in the transcript, leave the field empty or set it to `null` — invent nothing.
- Write in formal business English, factual and concise. No marketing phrases, no superlatives.
- For decisions with responsibility and deadline: record only what was explicitly agreed.

## Output
Return only a JSON object that conforms to the defined schema. Keep the JSON field names exactly as in the schema (they are in German). Start with the `_analyse` field (2-3 sentences on focus and field coverage), then fill the main fields.$en$,
    'fr', $fr$## Tâche
Rédigez un compte rendu structuré de la réunion d'affaires suivante.

## Format d'entrée
La transcription présente chaque intervention sous la forme `[Locuteur] : Texte`. Les noms sont fiables — attribuez les déclarations, décisions et tâches aux personnes concernées.

## Règles
- N'utilisez que les informations figurant dans la transcription.
- Si une information ne figure pas dans la transcription, laissez le champ vide ou mettez `null` — n'inventez rien.
- Rédigez en français formel, factuel et concis. Pas de formules marketing, pas de superlatifs.
- Pour les décisions avec responsable et échéance : ne consignez que ce qui a été convenu explicitement.

## Sortie
Renvoyez uniquement un objet JSON conforme au schéma défini. Conservez les noms de champs JSON exactement tels qu'ils figurent dans le schéma (ils sont en allemand). Commencez par le champ `_analyse` (2-3 phrases sur le sujet central et la couverture des champs), puis traitez les champs principaux.$fr$,
    'es', $es$## Tarea
Elabore un acta estructurada de la siguiente reunión de negocios.

## Formato de entrada
La transcripción muestra cada intervención como `[Interlocutor]: Texto`. Los nombres son fiables — atribuya las declaraciones, decisiones y tareas a las personas correspondientes.

## Reglas
- Utilice únicamente la información contenida en la transcripción.
- Si un dato no aparece en la transcripción, deje el campo vacío o asígnele `null` — no invente nada.
- Redacte en español formal, objetivo y conciso. Sin fórmulas de marketing ni superlativos.
- Para las decisiones con responsable y plazo: registre solo lo acordado de forma expresa.

## Salida
Devuelva únicamente un objeto JSON conforme al esquema definido. Mantenga los nombres de los campos JSON exactamente como aparecen en el esquema (están en alemán). Comience por el campo `_analyse` (2-3 frases sobre el enfoque y la cobertura de los campos) y, a continuación, complete los campos principales.$es$,
    'it', $it$## Compito
Redigere un verbale strutturato della seguente riunione aziendale.

## Formato di ingresso
La trascrizione riporta ogni intervento come `[Interlocutore]: Testo`. I nomi sono affidabili — attribuisca dichiarazioni, decisioni e compiti alle persone corrispondenti.

## Regole
- Utilizzi esclusivamente le informazioni contenute nella trascrizione.
- Se un'informazione non è presente nella trascrizione, lasci il campo vuoto o lo imposti su `null` — non inventi nulla.
- Scriva in italiano formale, oggettivo e conciso. Niente formule di marketing, niente superlativi.
- Per le decisioni con responsabile e scadenza: riporti solo quanto espressamente concordato.

## Output
Restituisca esclusivamente un oggetto JSON conforme allo schema definito. Mantenga i nomi dei campi JSON esattamente come nello schema (sono in tedesco). Inizi dal campo `_analyse` (2-3 frasi sul focus e sulla copertura dei campi), quindi completi i campi principali.$it$
  )::jsonb,
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
  jsonb_build_object(
    'de', $de$## Aufgabe
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
Gib ausschließlich ein JSON-Objekt nach dem definierten Schema zurück. Beginne mit dem Feld `_analyse` (2-3 Sätze zum Gesprächsschwerpunkt und welche Felder mangels Datenlage leer bleiben), arbeite dann die Hauptfelder ab.$de$,
    'en', $en$## Task
Produce a file note of the following client meeting.

## Input format
The transcript shows each speaker turn as `[Speaker]: Text`. Distinguish clearly between client statements (first-hand facts) and the adviser's assessments.

## Rules
- Strictly preserve attorney/tax-adviser confidentiality. Use no judgemental adjectives about the client or third parties.
- Provide no legal assessment of your own, no recommendations, no breach of the duty of confidentiality. Document only what was said in the meeting.
- For amounts, dates, deadlines and file references: reproduce them verbatim. No approximations.
- If a piece of information is not in the transcript (e.g. the fee was not discussed), leave the field empty or set it to `null` — invent nothing.
- Write in formal business English.

## Output
Return only a JSON object that conforms to the defined schema. Keep the JSON field names exactly as in the schema (they are in German). Start with the `_analyse` field (2-3 sentences on the focus of the conversation and which fields remain empty for lack of data), then fill the main fields.$en$,
    'fr', $fr$## Tâche
Rédigez une note de dossier du présent entretien avec le client.

## Format d'entrée
La transcription présente chaque intervention sous la forme `[Locuteur] : Texte`. Distinguez clairement les déclarations du client (faits de première main) et les appréciations de la conseillère ou du conseiller.

## Règles
- Respectez strictement le secret professionnel (avocat / conseil fiscal). Aucun adjectif de valeur à l'égard du client ou de tiers.
- Aucune appréciation juridique personnelle, aucune recommandation, aucune atteinte au secret du mandat. Documentez uniquement ce qui a été dit pendant l'entretien.
- Pour les montants, dates, délais et références de dossier : reproduction littérale exacte. Pas d'approximations.
- Si une information ne figure pas dans la transcription (p. ex. les honoraires n'ont pas été évoqués), laissez le champ vide ou mettez `null` — n'inventez rien.
- Rédigez en français formel.

## Sortie
Renvoyez uniquement un objet JSON conforme au schéma défini. Conservez les noms de champs JSON exactement tels qu'ils figurent dans le schéma (ils sont en allemand). Commencez par le champ `_analyse` (2-3 phrases sur le sujet central de l'entretien et les champs qui restent vides faute de données), puis traitez les champs principaux.$fr$,
    'es', $es$## Tarea
Elabore una nota de expediente del presente encuentro con el cliente.

## Formato de entrada
La transcripción muestra cada intervención como `[Interlocutor]: Texto`. Distinga claramente entre las declaraciones del cliente (hechos de primera mano) y las valoraciones del asesor o de la asesora.

## Reglas
- Respete estrictamente el secreto profesional (abogacía / asesoría fiscal). No emplee adjetivos valorativos sobre el cliente ni sobre terceros.
- No formule valoraciones jurídicas propias, ni recomendaciones, ni vulnere el secreto del mandato. Documente únicamente lo que se haya dicho en la conversación.
- En importes, fechas, plazos y referencias de expediente: reproducción literal exacta. Sin aproximaciones.
- Si un dato no aparece en la transcripción (p. ej. los honorarios no se trataron), deje el campo vacío o asígnele `null` — no invente nada.
- Redacte en español formal.

## Salida
Devuelva únicamente un objeto JSON conforme al esquema definido. Mantenga los nombres de los campos JSON exactamente como aparecen en el esquema (están en alemán). Comience por el campo `_analyse` (2-3 frases sobre el eje de la conversación y los campos que quedan vacíos por falta de datos) y, a continuación, complete los campos principales.$es$,
    'it', $it$## Compito
Redigere una nota di fascicolo del presente colloquio con il cliente.

## Formato di ingresso
La trascrizione riporta ogni intervento come `[Interlocutore]: Testo`. Distingua chiaramente fra le dichiarazioni del cliente (fatti di prima mano) e le valutazioni del consulente.

## Regole
- Rispetti rigorosamente il segreto professionale (avvocato / consulente fiscale). Niente aggettivi valutativi sul cliente o su terzi.
- Nessuna valutazione giuridica personale, nessuna raccomandazione, nessuna violazione del segreto del mandato. Documenti soltanto quanto detto nel colloquio.
- Per importi, date, scadenze e numeri di fascicolo: riproduzione letterale esatta. Nessuna approssimazione.
- Se un'informazione non è presente nella trascrizione (per esempio l'onorario non è stato trattato), lasci il campo vuoto o lo imposti su `null` — non inventi nulla.
- Scriva in italiano formale.

## Output
Restituisca esclusivamente un oggetto JSON conforme allo schema definito. Mantenga i nomi dei campi JSON esattamente come nello schema (sono in tedesco). Inizi dal campo `_analyse` (2-3 frasi sul focus del colloquio e sui campi che restano vuoti per mancanza di dati), quindi completi i campi principali.$it$
  )::jsonb,
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
  jsonb_build_object(
    'de', $de$## Aufgabe
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
Gib ausschließlich ein JSON-Objekt nach dem definierten Schema zurück. Beginne mit dem Feld `_analyse` (2-3 Sätze zum Gesprächsverlauf und worauf die Einschätzung fußt), arbeite dann die Hauptfelder ab.$de$,
    'en', $en$## Task
Evaluate the following sales conversation against the BANT framework.

## Input format
The transcript shows each speaker turn as `[Speaker]: Text`. Identify clearly who speaks on the customer side and who on the sales side, and attribute statements accordingly.

## Rules
- Stay strictly sober: no sales exaggeration, no wishful-thinking interpretations.
- BANT fields: fill only when the transcript provides concrete information. If a point was not asked or not answered, write literally "not asked" — do not guess.
- `verkaufschance_einschaetzung`: only one of the four enum values is allowed. Base the choice on concrete, quotable signals from the transcript.
- Reproduce objections verbatim or in close paraphrase.
- If information is missing: empty or `null` — invent nothing.
- Write in formal business English.

## Output
Return only a JSON object that conforms to the defined schema. Keep the JSON field names exactly as in the schema (they are in German). Start with the `_analyse` field (2-3 sentences on the course of the conversation and what the assessment rests on), then fill the main fields.$en$,
    'fr', $fr$## Tâche
Analysez l'entretien commercial suivant selon la grille BANT.

## Format d'entrée
La transcription présente chaque intervention sous la forme `[Locuteur] : Texte`. Identifiez clairement qui parle du côté client et qui du côté commercial, puis attribuez les déclarations en conséquence.

## Règles
- Restez strictement sobre : aucune exagération commerciale, aucune interprétation par anticipation favorable.
- Champs BANT : remplissez-les uniquement lorsque la transcription fournit des informations concrètes. Si un point n'a pas été demandé ou n'a pas reçu de réponse, écrivez littéralement « non demandé » — ne devinez pas.
- `verkaufschance_einschaetzung` : une seule des quatre valeurs d'énumération est autorisée. Fondez votre choix sur des signaux concrets et citables tirés de la transcription.
- Restituez les objections de manière littérale ou en paraphrase étroite.
- Si une information manque : vide ou `null` — n'inventez rien.
- Rédigez en français formel.

## Sortie
Renvoyez uniquement un objet JSON conforme au schéma défini. Conservez les noms de champs JSON exactement tels qu'ils figurent dans le schéma (ils sont en allemand). Commencez par le champ `_analyse` (2-3 phrases sur le déroulement de l'entretien et les bases de l'appréciation), puis traitez les champs principaux.$fr$,
    'es', $es$## Tarea
Analice la siguiente conversación comercial según el esquema BANT.

## Formato de entrada
La transcripción muestra cada intervención como `[Interlocutor]: Texto`. Identifique con claridad quién habla por el lado del cliente y quién por el lado comercial, y atribuya las declaraciones en consecuencia.

## Reglas
- Manténgase estrictamente objetivo: sin exageración comercial, sin interpretaciones complacientes.
- Campos BANT: cumpliméntelos solo cuando la transcripción aporte datos concretos. Si un punto no se ha preguntado o no se ha contestado, escriba literalmente «no preguntado» — no especule.
- `verkaufschance_einschaetzung`: solo se admite uno de los cuatro valores de la enumeración. Fundamente la elección en señales concretas y citables de la transcripción.
- Reproduzca las objeciones de forma literal o en paráfrasis cercana.
- Si falta información: vacío o `null` — no invente nada.
- Redacte en español formal.

## Salida
Devuelva únicamente un objeto JSON conforme al esquema definido. Mantenga los nombres de los campos JSON exactamente como aparecen en el esquema (están en alemán). Comience por el campo `_analyse` (2-3 frases sobre el desarrollo de la conversación y los fundamentos de la valoración) y, a continuación, complete los campos principales.$es$,
    'it', $it$## Compito
Valuti il seguente colloquio commerciale secondo lo schema BANT.

## Formato di ingresso
La trascrizione riporta ogni intervento come `[Interlocutore]: Testo`. Identifichi con chiarezza chi interviene dal lato cliente e chi dal lato commerciale, e attribuisca le dichiarazioni di conseguenza.

## Regole
- Resti rigorosamente sobrio: nessuna esagerazione commerciale, nessuna interpretazione di comodo.
- Campi BANT: li compili solo quando la trascrizione fornisce indicazioni concrete. Se un punto non è stato chiesto o non ha ricevuto risposta, scriva letteralmente «non chiesto» — non ipotizzi.
- `verkaufschance_einschaetzung`: è ammesso uno solo dei quattro valori dell'enumerazione. Fondi la scelta su segnali concreti e citabili dalla trascrizione.
- Riproduca le obiezioni in forma letterale o in parafrasi stretta.
- Se manca un'informazione: vuoto o `null` — non inventi nulla.
- Scriva in italiano formale.

## Output
Restituisca esclusivamente un oggetto JSON conforme allo schema definito. Mantenga i nomi dei campi JSON esattamente come nello schema (sono in tedesco). Inizi dal campo `_analyse` (2-3 frasi sull'andamento del colloquio e sui fondamenti della valutazione), quindi completi i campi principali.$it$
  )::jsonb,
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
  jsonb_build_object(
    'de', $de$## Aufgabe
Erstelle ein Protokoll des folgenden Jahresgesprächs für die Kundenakte.

## Eingabeformat
Das Transkript zeigt jeden Sprecherbeitrag als `[Sprecher]: Text`. Die Namen sind verlässlich — attribuiere Aussagen, Beschlüsse und Wünsche den richtigen Personen.

## Regeln
- Risikoveränderungen seit dem Vorjahr klar herausarbeiten: gestiegen, gesunken, neu, weggefallen.
- Cross-Selling-Potenziale notieren, ohne aufdringlich oder verkäuferisch zu wirken — neutrale Beobachtung.
- Wiedervorlage-Datum sinnvoll setzen (typisch: nächstes Jahresgespräch in 12 Monaten, früher wenn das Transkript es nahelegt).
- Wenn eine Information nicht im Transkript steht, lass das Feld leer oder setze es auf `null` — nicht erfinden.
- Schreibe in formellem Deutsch.

## Ausgabe
Gib ausschließlich ein JSON-Objekt nach dem definierten Schema zurück. Beginne mit dem Feld `_analyse` (2-3 Sätze zum Gesundheitszustand der Kundenbeziehung), arbeite dann die Hauptfelder ab.$de$,
    'en', $en$## Task
Produce a record of the following annual review meeting for the customer file.

## Input format
The transcript shows each speaker turn as `[Speaker]: Text`. The names are reliable — attribute statements, decisions and requests to the respective persons.

## Rules
- Make changes in risk since the previous year explicit: increased, decreased, new, removed.
- Note cross-sell potential as a neutral observation, without being pushy or sales-like.
- Set a sensible follow-up date (typically: next annual review in 12 months, earlier if the transcript suggests so).
- If a piece of information is not in the transcript, leave the field empty or set it to `null` — invent nothing.
- Write in formal business English.

## Output
Return only a JSON object that conforms to the defined schema. Keep the JSON field names exactly as in the schema (they are in German). Start with the `_analyse` field (2-3 sentences on the health of the customer relationship), then fill the main fields.$en$,
    'fr', $fr$## Tâche
Rédigez un compte rendu de l'entretien annuel suivant pour le dossier client.

## Format d'entrée
La transcription présente chaque intervention sous la forme `[Locuteur] : Texte`. Les noms sont fiables — attribuez les déclarations, décisions et souhaits aux personnes concernées.

## Règles
- Faites clairement ressortir les évolutions du risque depuis l'année précédente : augmenté, diminué, nouveau, disparu.
- Notez les potentiels de vente additionnelle comme observation neutre, sans tournure commerciale insistante.
- Fixez une date de relance pertinente (typiquement : prochain entretien annuel dans 12 mois, plus tôt si la transcription le suggère).
- Si une information ne figure pas dans la transcription, laissez le champ vide ou mettez `null` — n'inventez rien.
- Rédigez en français formel.

## Sortie
Renvoyez uniquement un objet JSON conforme au schéma défini. Conservez les noms de champs JSON exactement tels qu'ils figurent dans le schéma (ils sont en allemand). Commencez par le champ `_analyse` (2-3 phrases sur la santé de la relation client), puis traitez les champs principaux.$fr$,
    'es', $es$## Tarea
Elabore un acta del siguiente encuentro anual para el expediente del cliente.

## Formato de entrada
La transcripción muestra cada intervención como `[Interlocutor]: Texto`. Los nombres son fiables — atribuya las declaraciones, decisiones y deseos a las personas correspondientes.

## Reglas
- Destaque con claridad las variaciones del riesgo frente al año anterior: aumentado, disminuido, nuevo, eliminado.
- Anote los potenciales de venta cruzada como observación neutra, sin tono comercial insistente.
- Establezca una fecha de seguimiento razonable (típicamente: próximo encuentro anual dentro de 12 meses, antes si la transcripción lo sugiere).
- Si un dato no aparece en la transcripción, deje el campo vacío o asígnele `null` — no invente nada.
- Redacte en español formal.

## Salida
Devuelva únicamente un objeto JSON conforme al esquema definido. Mantenga los nombres de los campos JSON exactamente como aparecen en el esquema (están en alemán). Comience por el campo `_analyse` (2-3 frases sobre el estado de la relación con el cliente) y, a continuación, complete los campos principales.$es$,
    'it', $it$## Compito
Redigere un verbale del seguente colloquio annuale per il fascicolo del cliente.

## Formato di ingresso
La trascrizione riporta ogni intervento come `[Interlocutore]: Testo`. I nomi sono affidabili — attribuisca dichiarazioni, decisioni e desideri alle persone corrispondenti.

## Regole
- Evidenzi con chiarezza le variazioni del rischio rispetto all'anno precedente: aumentato, diminuito, nuovo, venuto meno.
- Annoti i potenziali di cross-selling come osservazione neutra, senza tono commerciale insistente.
- Fissi una data di richiamo sensata (di norma: prossimo colloquio annuale fra 12 mesi, prima se la trascrizione lo suggerisce).
- Se un'informazione non è presente nella trascrizione, lasci il campo vuoto o lo imposti su `null` — non inventi nulla.
- Scriva in italiano formale.

## Output
Restituisca esclusivamente un oggetto JSON conforme allo schema definito. Mantenga i nomi dei campi JSON esattamente come nello schema (sono in tedesco). Inizi dal campo `_analyse` (2-3 frasi sullo stato della relazione con il cliente), quindi completi i campi principali.$it$
  )::jsonb,
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
  system_prompts   = excluded.system_prompts,
  output_schema    = excluded.output_schema,
  few_shot_input   = excluded.few_shot_input,
  few_shot_output  = excluded.few_shot_output,
  is_system        = excluded.is_system,
  is_active        = excluded.is_active,
  version          = excluded.version,
  updated_at       = now();
