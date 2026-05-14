-- ========================================================================
-- 0005_webhooks_api_keys.sql
-- Outgoing webhooks + API keys for the external REST API.
--
-- Lets an org-owner configure 0..n webhook URLs that receive a signed POST
-- whenever a meeting transitions state (created / ready / failed / updated
-- / deleted), and 0..n API keys that authenticate external read access to
-- meetings + their markdown export.
--
-- Webhook secrets stay in clear text (we need them to sign payloads on
-- every dispatch). API-key TOKENS are stored only as bcrypt hashes — the
-- raw token is returned exactly once at creation.
-- ========================================================================

-- ─── Webhooks ───────────────────────────────────────────────────────────

create table if not exists public.org_webhooks (
  id                uuid primary key default uuid_generate_v4(),
  org_id            uuid not null references public.orgs(id) on delete cascade,
  url               text not null,
  secret            text not null,                              -- HMAC-SHA256 key
  -- Allowed event names: meeting.created, meeting.ready,
  -- meeting.failed, meeting.deleted, meeting.updated.
  events            text[] not null default array['meeting.ready']::text[],
  is_active         boolean not null default true,
  description       text not null default '',
  created_at        timestamptz not null default now(),
  created_by        uuid references public.users(id),
  last_success_at   timestamptz,
  last_failure_at   timestamptz,
  last_failure_msg  text
);

create index if not exists org_webhooks_org_idx
  on public.org_webhooks (org_id) where is_active = true;

-- ─── Webhook delivery audit (last N per webhook) ───────────────────────

create table if not exists public.webhook_deliveries (
  id              uuid primary key default uuid_generate_v4(),
  webhook_id      uuid not null references public.org_webhooks(id) on delete cascade,
  meeting_id      uuid references public.meetings(id) on delete set null,
  event           text not null,
  status_code     int,                                          -- null = transport error
  response_body   text,                                         -- first 512 chars
  error_message   text,
  attempt         int not null default 1,
  created_at      timestamptz not null default now()
);

create index if not exists webhook_deliveries_webhook_idx
  on public.webhook_deliveries (webhook_id, created_at desc);

-- ─── API Keys ──────────────────────────────────────────────────────────

create table if not exists public.api_keys (
  id            uuid primary key default uuid_generate_v4(),
  org_id        uuid not null references public.orgs(id) on delete cascade,
  name          text not null,                                  -- user-supplied label
  key_prefix    text not null,                                  -- first ~12 chars, for UI
  key_hash      text not null,                                  -- bcrypt
  scopes        text[] not null default array['read:meetings']::text[],
  created_at    timestamptz not null default now(),
  created_by    uuid references public.users(id),
  last_used_at  timestamptz,
  revoked_at    timestamptz
);

create index if not exists api_keys_org_idx
  on public.api_keys (org_id) where revoked_at is null;

-- Looking up by prefix narrows the candidate set for bcrypt-verify down
-- to ~1 row on average (12-char random prefix).
create index if not exists api_keys_prefix_idx
  on public.api_keys (key_prefix) where revoked_at is null;

-- ─── Touch-trigger for the few mutable columns above ─────────────────

-- (We do NOT want a generic updated_at column on these tables — the
-- last_success_at / last_failure_at / last_used_at fields carry the
-- relevant timestamps already.)

-- ─── Row Level Security ────────────────────────────────────────────────

alter table public.org_webhooks       enable row level security;
alter table public.webhook_deliveries enable row level security;
alter table public.api_keys           enable row level security;

-- org_webhooks: every member of the org may read; writes go via the
-- backend, which does its own checks. We follow the org_settings pattern
-- (no role-gate at the RLS layer, app layer enforces it).
drop policy if exists org_webhooks_select on public.org_webhooks;
create policy org_webhooks_select on public.org_webhooks
  for select
  using (org_id in (select public.current_user_orgs()));

drop policy if exists org_webhooks_modify on public.org_webhooks;
create policy org_webhooks_modify on public.org_webhooks
  for all
  using (org_id in (select public.current_user_orgs()))
  with check (org_id in (select public.current_user_orgs()));

-- webhook_deliveries: read-only via app; the worker writes with
-- superuser privileges (RLS bypassed for that connection).
drop policy if exists webhook_deliveries_select on public.webhook_deliveries;
create policy webhook_deliveries_select on public.webhook_deliveries
  for select
  using (
    webhook_id in (
      select id from public.org_webhooks
      where org_id in (select public.current_user_orgs())
    )
  );

-- api_keys: members of the org can list/manage. Raw key_hash never
-- leaves the backend; the API response shape strips it.
drop policy if exists api_keys_select on public.api_keys;
create policy api_keys_select on public.api_keys
  for select
  using (org_id in (select public.current_user_orgs()));

drop policy if exists api_keys_modify on public.api_keys;
create policy api_keys_modify on public.api_keys
  for all
  using (org_id in (select public.current_user_orgs()))
  with check (org_id in (select public.current_user_orgs()));
