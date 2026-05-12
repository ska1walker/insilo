-- ========================================================================
-- 0002_rls_policies.sql
-- Row Level Security für alle Org-gebundenen Tabellen.
--
-- Wichtig: Bei Olares haben wir keine auth.users-Tabelle (kein Supabase Auth).
-- Stattdessen setzen wir bei jedem DB-Connection-Open per
--   SET LOCAL app.current_user_id = '<uuid>';
-- den User-Kontext, basierend auf dem X-Bfl-User Header.
-- Die RLS-Policies lesen diesen Wert.
-- ========================================================================

-- ========================================================================
-- Helper Functions
-- ========================================================================

-- Aktuelle User-ID aus Session-Variable lesen
create or replace function public.current_user_id()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('app.current_user_id', true), '')::uuid;
$$;

-- Welche Orgs gehören zum aktuellen User?
create or replace function public.current_user_orgs()
returns setof uuid
language sql
stable
as $$
  select org_id from public.user_org_roles
  where user_id = public.current_user_id();
$$;

-- Welche Rolle hat der aktuelle User in einer Org?
create or replace function public.current_user_role_in_org(target_org uuid)
returns public.user_role
language sql
stable
as $$
  select role from public.user_org_roles
  where user_id = public.current_user_id() and org_id = target_org;
$$;

-- ========================================================================
-- RLS aktivieren
-- ========================================================================

alter table public.orgs enable row level security;
alter table public.user_org_roles enable row level security;
alter table public.users enable row level security;
alter table public.meetings enable row level security;
alter table public.transcripts enable row level security;
alter table public.summaries enable row level security;
alter table public.templates enable row level security;
alter table public.meeting_chunks enable row level security;
alter table public.tags enable row level security;
alter table public.meeting_tags enable row level security;
alter table public.audit_log enable row level security;

-- ========================================================================
-- USERS
-- ========================================================================

-- User sieht nur sich selbst und User, mit denen er eine Org teilt
create policy users_select on public.users
  for select
  using (
    id = public.current_user_id()
    or id in (
      select user_id from public.user_org_roles
      where org_id in (select public.current_user_orgs())
    )
  );

-- ========================================================================
-- ORGS
-- ========================================================================

create policy orgs_select on public.orgs
  for select
  using (id in (select public.current_user_orgs()));

create policy orgs_update on public.orgs
  for update
  using (public.current_user_role_in_org(id) in ('owner', 'admin'));

-- ========================================================================
-- USER_ORG_ROLES
-- ========================================================================

create policy user_org_roles_select on public.user_org_roles
  for select
  using (
    user_id = public.current_user_id()
    or org_id in (select public.current_user_orgs())
  );

create policy user_org_roles_modify on public.user_org_roles
  for all
  using (public.current_user_role_in_org(org_id) in ('owner', 'admin'));

-- ========================================================================
-- MEETINGS
-- ========================================================================

create policy meetings_select on public.meetings
  for select
  using (
    org_id in (select public.current_user_orgs())
    and deleted_at is null
  );

create policy meetings_insert on public.meetings
  for insert
  with check (
    org_id in (select public.current_user_orgs())
    and created_by = public.current_user_id()
  );

create policy meetings_update on public.meetings
  for update
  using (
    org_id in (select public.current_user_orgs())
    and (
      created_by = public.current_user_id()
      or public.current_user_role_in_org(org_id) in ('owner', 'admin')
    )
  );

create policy meetings_delete on public.meetings
  for delete
  using (public.current_user_role_in_org(org_id) in ('owner', 'admin'));

-- ========================================================================
-- TRANSCRIPTS
-- ========================================================================

create policy transcripts_select on public.transcripts
  for select
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
      and deleted_at is null
    )
  );

-- Inserts kommen vom Worker mit Bypass-Role, kein RLS-Eintrag nötig

-- ========================================================================
-- SUMMARIES
-- ========================================================================

create policy summaries_select on public.summaries
  for select
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
      and deleted_at is null
    )
  );

-- ========================================================================
-- TEMPLATES
-- ========================================================================

create policy templates_select on public.templates
  for select
  using (
    is_active = true
    and (
      is_system = true
      or org_id in (select public.current_user_orgs())
    )
  );

create policy templates_insert on public.templates
  for insert
  with check (
    org_id in (select public.current_user_orgs())
    and public.current_user_role_in_org(org_id) in ('owner', 'admin')
    and is_system = false
  );

create policy templates_update on public.templates
  for update
  using (
    org_id in (select public.current_user_orgs())
    and public.current_user_role_in_org(org_id) in ('owner', 'admin')
    and is_system = false
  );

-- ========================================================================
-- MEETING CHUNKS
-- ========================================================================

create policy meeting_chunks_select on public.meeting_chunks
  for select
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
      and deleted_at is null
    )
  );

-- ========================================================================
-- TAGS
-- ========================================================================

create policy tags_all on public.tags
  for all
  using (org_id in (select public.current_user_orgs()));

create policy meeting_tags_all on public.meeting_tags
  for all
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
    )
  );

-- ========================================================================
-- AUDIT LOG (Append-only)
-- ========================================================================

create policy audit_log_select on public.audit_log
  for select
  using (
    user_id = public.current_user_id()
    or (
      org_id in (select public.current_user_orgs())
      and public.current_user_role_in_org(org_id) in ('owner', 'admin')
    )
  );

-- Append-only Enforcement
create policy audit_log_no_update on public.audit_log for update using (false);
create policy audit_log_no_delete on public.audit_log for delete using (false);
