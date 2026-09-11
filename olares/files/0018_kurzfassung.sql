-- ============================================================================
-- 0018 — Eine Kurzfassung in die Werks-Vorlagen
--
-- **Der Anlass.** Wer nach einer Aufnahme auf die Besprechung schaut,
-- bekam sechs bis zehn Felder gleichen Gewichts und darunter den
-- vollständigen Wortlaut. Was die Besprechung *ergeben* hat, stand
-- nirgends in einem Satz: `kernthemen` ist eine Stichpunktliste, keine
-- Prosa.
--
-- Die Oberfläche ordnet die Felder seit v0.1.91 nach Rang (Kopf und
-- „Mehr", siehe `backend/app/exports/markdown.py`) — das allein macht
-- aber keine Kurzfassung, wenn keine im Schema steht. Also hier.
--
-- **Vier Vorlagen, nicht fünf.** Die Schnellnotiz bekommt keine: sie ist
-- die Kurzfassung. Ihr `kerninhalt` steht ohnehin im Kopf.
--
-- **Was mit vorhandenen Zusammenfassungen passiert: nichts.** Das Feld
-- gilt für künftige Läufe. Wer es für eine alte Besprechung will, drückt
-- „Erneut zusammenfassen". Ein stiller Neulauf über alle Besprechungen
-- wäre ein Sprachmodell-Aufruf je Zeile, ohne dass jemand darum gebeten
-- hat — und bei einem externen Endpunkt eine Ausleitung obendrein.
--
-- **`required` statt Prompt-Text.** Die Aufforderung steht im Schema,
-- nicht in fünf mal vier Prompt-Texten: das Sprachmodell antwortet im
-- JSON-Modus gegen genau dieses Schema, und ein Pflichtfeld mit
-- Beschreibung trägt dort weiter als ein Satz im Fließtext. Ob das
-- wirklich reicht, gehört gegen das laufende Modell gemessen, nicht
-- behauptet.
-- ============================================================================

-- Die Beschreibung ist das, was das Modell liest. Sie sagt die Länge, die
-- Blickrichtung („was ergab sich") und was nicht hineingehört.
create or replace function public._kurzfassung_feld()
returns jsonb language sql immutable as $$
  select jsonb_build_object(
    'type', 'string',
    'description',
      'Zwei bis vier Sätze: Was hat diese Besprechung ergeben? '
      'Ergebnis und Folgen, nicht der Ablauf. Keine Aufzählung, keine '
      'Wiederholung der Einzelfelder, keine Einleitung wie "In diesem '
      'Meeting wurde besprochen". Wenn das Transkript zu wenig hergibt, '
      'lass das Feld leer.'
  );
$$;

update public.templates
set output_schema = jsonb_set(
      jsonb_set(
        output_schema,
        '{properties,kurzfassung}',
        public._kurzfassung_feld(),
        true
      ),
      '{required}',
      -- Vorn anhängen: die Reihenfolge in `required` ist zugleich die
      -- Reihenfolge, in der das Modell die Felder abarbeitet. `_analyse`
      -- bleibt davor — erst denken, dann zusammenfassen.
      (
        select jsonb_agg(wert order by rang)
        from (
          select to_jsonb('_analyse'::text) as wert, 0 as rang
          union all
          select to_jsonb('kurzfassung'::text), 1
          union all
          select w.wert, 2 + w.pos
          from jsonb_array_elements(coalesce(output_schema->'required', '[]'::jsonb))
               with ordinality as w(wert, pos)
          where w.wert not in (to_jsonb('_analyse'::text), to_jsonb('kurzfassung'::text))
        ) as felder
      ),
      true
    ),
    version = version + 1,
    updated_at = now()
where is_system = true
  and id in (
    '00000000-0000-0000-0000-000000000001',  -- Allgemeine Besprechung
    '00000000-0000-0000-0000-000000000002',  -- Mandantengespräch
    '00000000-0000-0000-0000-000000000003',  -- Vertriebsgespräch
    '00000000-0000-0000-0000-000000000004'   -- Jahresgespräch
  )
  and not (output_schema->'properties' ? 'kurzfassung');

drop function public._kurzfassung_feld();

comment on column public.templates.output_schema is
  'JSON-Schema der Zusammenfassung. Eine Eigenschaft darf "x-rang" tragen '
  '("kopf" oder "mehr") und bestimmt damit, ob das Feld in der Ansicht oben '
  'steht oder unter "Mehr" liegt. Ohne Angabe entscheidet die Vorbelegung in '
  'backend/app/exports/markdown.py:KOPF_FELDER.';
