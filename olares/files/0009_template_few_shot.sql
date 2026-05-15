-- ========================================================================
-- 0009_template_few_shot.sql
-- Per-template few-shot example for v0.1.40 prompt quality iteration.
--
-- For Qwen2.5 14B Q4_K_M (the on-prem default on Olares), one
-- hand-curated user→assistant example before the real meeting cuts
-- hallucinations and tightens JSON shape adherence noticeably. The
-- example lives ON the template — same lifecycle as system_prompt +
-- output_schema, so customising a template via the UI continues to
-- behave intuitively.
--
-- Both columns are nullable: legacy templates without an example keep
-- working (summarize.py just sends the system + real-user messages).
-- ========================================================================

alter table public.templates
  add column if not exists few_shot_input  text;

alter table public.templates
  add column if not exists few_shot_output jsonb;
