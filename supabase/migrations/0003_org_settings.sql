-- ========================================================================
-- 0003_org_settings.sql
-- Per-org LLM configuration.
--
-- Lets each Olares-box owner point Insilo at any OpenAI-compatible
-- endpoint (their own LiteLLM gateway, a local Ollama, an external API,
-- ...) without touching the Helm chart. Empty values mean "fall back to
-- the env defaults baked into the deployment."
-- ========================================================================

create table if not exists public.org_settings (
  org_id        uuid primary key references public.orgs(id) on delete cascade,
  llm_base_url  text not null default '',
  llm_api_key   text not null default '',
  llm_model     text not null default '',
  updated_at    timestamptz not null default now(),
  updated_by    uuid references public.users(id)
);

create or replace function public.touch_org_settings_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_org_settings_updated_at on public.org_settings;
create trigger trg_org_settings_updated_at
  before update on public.org_settings
  for each row execute function public.touch_org_settings_updated_at();

-- RLS: every org sees its own row, owner/admin may write.
alter table public.org_settings enable row level security;

drop policy if exists org_settings_select on public.org_settings;
create policy org_settings_select on public.org_settings
  for select
  using (org_id in (select public.current_user_orgs()));

drop policy if exists org_settings_upsert on public.org_settings;
create policy org_settings_upsert on public.org_settings
  for all
  using (org_id in (select public.current_user_orgs()))
  with check (org_id in (select public.current_user_orgs()));
