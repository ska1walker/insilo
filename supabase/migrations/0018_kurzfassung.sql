-- ============================================================================
-- 0018 — Der Rang eines Feldes, dokumentiert an der Spalte
--
-- **Hier stand einmal mehr.** Der erste Entwurf fügte den Werks-Vorlagen
-- per `update` ein Feld `kurzfassung` hinzu. Das war wirkungslos, und das
-- ließ sich erst auf der Box sehen:
--
--   Applying /sql/0018_kurzfassung.sql...  ok
--   Applying /sql/0099_seed.sql...         ok
--
-- Der Init-Container führt **jede** Datei unter `/sql/` bei **jedem**
-- Start aus (siehe `olares/templates/deployment-backend.yaml`), und
-- `0099_seed.sql` endet mit
--
--   on conflict (id) do update set output_schema = excluded.output_schema,
--                                  version = excluded.version, …
--
-- Der Seed ist damit die Quelle für die Werks-Vorlagen, und zwar bei
-- jedem Neustart. Eine Migration, die daran etwas ändert, wird
-- Sekundenbruchteile später überschrieben. Aufgefallen ist es an der
-- Versionsziffer: sie stand nach dem Ausrollen auf 2, obwohl die
-- Migration auf 3 hochgezählt hätte.
--
-- **Die Lehre, und sie gilt für die nächste Migration genauso:** was
-- `seed.sql` besitzt, gehört in `seed.sql`. Das Feld `kurzfassung` steht
-- deshalb dort — samt erhöhter `version`.
--
-- Übrig bleibt hier, was nur eine Migration kann: ein Kommentar an der
-- Spalte. Der Seed schreibt Zeilen, keine Metadaten.
-- ============================================================================

comment on column public.templates.output_schema is
  'JSON-Schema der Zusammenfassung. Eine Eigenschaft darf "x-rang" tragen '
  '("kopf" oder "mehr") und bestimmt damit, ob das Feld in der Ansicht oben '
  'steht oder unter "Mehr" liegt. Ohne Angabe entscheidet die Vorbelegung in '
  'backend/app/exports/markdown.py:KOPF_FELDER. Die Werks-Vorlagen selbst '
  'kommen aus supabase/seed.sql und werden bei jedem Backend-Start neu '
  'geschrieben — wer sie ändern will, ändert sie dort, nicht in einer '
  'Migration.';
