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
update public.templates
   set system_prompts = jsonb_build_object('de', system_prompt)
 where system_prompt is not null
   and (system_prompts = '{}'::jsonb or system_prompts is null);

update public.template_customizations
   set system_prompts = jsonb_build_object('de', system_prompt)
 where system_prompt is not null
   and (system_prompts = '{}'::jsonb or system_prompts is null);
