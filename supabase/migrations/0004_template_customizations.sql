-- ========================================================================
-- 0004_template_customizations.sql
-- Per-org override of a template's system prompt.
--
-- The 4 seed templates (Allgemeine Besprechung, Jahresgespräch, …) ship
-- with sensible defaults. An org can tailor the prompt to their domain
-- (legal phrasing for Mandantengespräch, sales-funnel vocabulary for
-- Vertriebsgespräch, …) without forking the template row itself. Deleting
-- the customization row reverts the org to the system default.
-- ========================================================================

create table if not exists public.template_customizations (
  org_id          uuid not null references public.orgs(id) on delete cascade,
  template_id     uuid not null references public.templates(id) on delete cascade,
  system_prompt   text not null,
  updated_at      timestamptz not null default now(),
  updated_by      uuid references public.users(id),
  primary key (org_id, template_id)
);

drop trigger if exists trg_template_customizations_updated_at on public.template_customizations;
create trigger trg_template_customizations_updated_at
  before update on public.template_customizations
  for each row execute function public.touch_org_settings_updated_at();
  -- (re-uses the helper from 0003 — same "stamp updated_at on update" pattern)

alter table public.template_customizations enable row level security;

drop policy if exists template_customizations_select on public.template_customizations;
create policy template_customizations_select on public.template_customizations
  for select
  using (org_id in (select public.current_user_orgs()));

drop policy if exists template_customizations_upsert on public.template_customizations;
create policy template_customizations_upsert on public.template_customizations
  for all
  using (org_id in (select public.current_user_orgs()))
  with check (org_id in (select public.current_user_orgs()));
