-- ========================================================================
-- 0002_rls_policies.sql
-- Row Level Security for all tenant-scoped tables
-- ========================================================================

-- Enable RLS on all relevant tables
alter table public.orgs enable row level security;
alter table public.user_org_roles enable row level security;
alter table public.meetings enable row level security;
alter table public.transcripts enable row level security;
alter table public.summaries enable row level security;
alter table public.templates enable row level security;
alter table public.meeting_chunks enable row level security;
alter table public.tags enable row level security;
alter table public.meeting_tags enable row level security;
alter table public.audit_log enable row level security;

-- ========================================================================
-- Helper Function: which orgs does the current user belong to?
-- ========================================================================

create or replace function public.current_user_orgs()
returns setof uuid
language sql
stable
security definer
set search_path = public
as $$
  select org_id from public.user_org_roles where user_id = auth.uid();
$$;

create or replace function public.current_user_role_in_org(target_org uuid)
returns public.user_role
language sql
stable
security definer
set search_path = public
as $$
  select role from public.user_org_roles
  where user_id = auth.uid() and org_id = target_org;
$$;

-- ========================================================================
-- ORGS
-- ========================================================================

create policy orgs_select on public.orgs
  for select
  using (id in (select public.current_user_orgs()));

create policy orgs_update on public.orgs
  for update
  using (
    public.current_user_role_in_org(id) in ('owner', 'admin')
  );

-- ========================================================================
-- USER_ORG_ROLES
-- ========================================================================

create policy user_org_roles_select on public.user_org_roles
  for select
  using (
    user_id = auth.uid()
    or org_id in (select public.current_user_orgs())
  );

create policy user_org_roles_insert on public.user_org_roles
  for insert
  with check (
    public.current_user_role_in_org(org_id) in ('owner', 'admin')
  );

create policy user_org_roles_delete on public.user_org_roles
  for delete
  using (
    public.current_user_role_in_org(org_id) in ('owner', 'admin')
  );

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
    and created_by = auth.uid()
  );

create policy meetings_update on public.meetings
  for update
  using (
    org_id in (select public.current_user_orgs())
    and (
      created_by = auth.uid()
      or public.current_user_role_in_org(org_id) in ('owner', 'admin')
    )
  );

create policy meetings_soft_delete on public.meetings
  for delete
  using (
    public.current_user_role_in_org(org_id) in ('owner', 'admin')
  );

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

-- Inserts/Updates kommen vom Backend-Service (service_role), nicht von Usern

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

create policy tags_select on public.tags
  for select
  using (org_id in (select public.current_user_orgs()));

create policy tags_insert on public.tags
  for insert
  with check (org_id in (select public.current_user_orgs()));

create policy tags_update on public.tags
  for update
  using (org_id in (select public.current_user_orgs()));

create policy tags_delete on public.tags
  for delete
  using (org_id in (select public.current_user_orgs()));

-- ========================================================================
-- MEETING_TAGS
-- ========================================================================

create policy meeting_tags_select on public.meeting_tags
  for select
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
      and deleted_at is null
    )
  );

create policy meeting_tags_insert on public.meeting_tags
  for insert
  with check (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
    )
  );

create policy meeting_tags_delete on public.meeting_tags
  for delete
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
    )
  );

-- ========================================================================
-- AUDIT LOG
-- ========================================================================

-- User sieht eigene Aktionen, Admin sieht alle Org-Aktionen
create policy audit_log_select on public.audit_log
  for select
  using (
    user_id = auth.uid()
    or (
      org_id in (select public.current_user_orgs())
      and public.current_user_role_in_org(org_id) in ('owner', 'admin')
    )
  );

-- Inserts kommen vom Backend (service_role)
