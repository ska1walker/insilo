-- ========================================================================
-- 0013_drop_legacy_system_prompt.sql
-- Drop legacy TEXT prompt slots + meetings.language default (v0.1.48).
--
-- Hintergrund:
--   * Seit Migration 0012 existieren `templates.system_prompts JSONB`
--     und `template_customizations.system_prompts JSONB` mit Backfill
--     `{ "de": <legacy prompt> }`. Der Resolver in summarize.py liest
--     bevorzugt aus der JSONB-Map. In v0.1.48 wurden alle Lese- und
--     Schreib-Sites auf die JSONB-Variante umgestellt — die TEXT-Spalten
--     sind tot.
--   * `meetings.language` hatte einen Hardcoded-Default `'de'`, der den
--     v0.1.48-Selector (User-Choice incl. Auto-Detect) unterläuft.
--     NULL = Whisper auto-detect, alles andere = ISO-Code.
--
-- Eine Rückkehr zur TEXT-Spalte ist nicht vorgesehen. Bei Rollback der
-- Helm-Revision würde die Init-Container-Migration den DROP wiederholen
-- (idempotent durch IF EXISTS), die Spalte bliebe weg.
-- ========================================================================

alter table public.templates
  drop column if exists system_prompt;

alter table public.template_customizations
  drop column if exists system_prompt;

alter table public.meetings
  alter column language drop default;
