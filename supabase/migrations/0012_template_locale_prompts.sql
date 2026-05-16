-- ========================================================================
-- 0012_template_locale_prompts.sql
-- LLM-Prompts pro UI-Sprache (v0.1.46+).
--
-- Bisher hat jedes Template einen einzelnen `system_prompt TEXT`-Slot
-- — die LLM antwortet entsprechend nur in der Sprache dieses Prompts
-- (de). Mit der vollständigen UI-i18n (v0.1.43–v0.1.45) muss auch das
-- LLM-Output zur User-Sprache passen.
--
-- Migration-Strategie:
--   1. Neue Spalte `system_prompts JSONB` mit Map `{de,en,fr,es,it}`.
--   2. Backfill: existierender `system_prompt` → `system_prompts.de`.
--   3. `system_prompt TEXT` bleibt zunächst aktiv (Backward-Compat) —
--      summarize.py liest `coalesce(system_prompts->>locale,
--      system_prompts->>'de', system_prompt)`.
--   4. Drop von `system_prompt` erfolgt in einer späteren Migration,
--      wenn alle Code-Pfade auf JSONB umgestellt sind.
--
-- Selbe Logik für `template_customizations` — Org-Overrides müssen
-- ebenfalls pro Sprache geführt werden, sonst überschreibt eine
-- deutsche Customization den englischen Default.
-- ========================================================================

alter table public.templates
  add column if not exists system_prompts jsonb not null default '{}'::jsonb;

alter table public.template_customizations
  add column if not exists system_prompts jsonb not null default '{}'::jsonb;

-- Backfill: bestehende deutschen Prompts in die JSONB-Map heben.
-- Nur, wo das Ziel noch leer ist — idempotent bei Re-Runs.
--
-- ACHTUNG (nachträglich angepasst in v0.1.50): das Backfill-UPDATE wird
-- in eine DO-Block gewrapped, der prüft ob die Legacy-Spalte überhaupt
-- noch existiert. Hintergrund: Migration 0013 dropt `system_prompt`.
-- Der Init-Container-Runner versucht beim Re-Deploy alle SQL-Files in
-- Reihenfolge erneut — ohne diesen Guard schlägt 0012 dann fehl, weil
-- die referenzierte Spalte weg ist. Bei First-Install (Spalte existiert
-- noch beim 0012-Run, 0013 droppt erst danach) läuft der Backfill
-- normal durch.
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'templates'
      and column_name = 'system_prompt'
  ) then
    execute $sql$
      update public.templates
         set system_prompts = jsonb_build_object('de', system_prompt)
       where system_prompt is not null
         and (system_prompts = '{}'::jsonb or system_prompts is null)
    $sql$;
  end if;
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'template_customizations'
      and column_name = 'system_prompt'
  ) then
    execute $sql$
      update public.template_customizations
         set system_prompts = jsonb_build_object('de', system_prompt)
       where system_prompt is not null
         and (system_prompts = '{}'::jsonb or system_prompts is null)
    $sql$;
  end if;
end $$;
