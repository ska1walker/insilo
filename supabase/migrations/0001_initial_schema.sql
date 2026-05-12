-- ========================================================================
-- 0001_initial_schema.sql
-- Initial database schema for Insilo on Olares
--
-- Hinweis: Keine auth.users-Tabelle (wie bei Supabase) — User-Identität
-- kommt vom Olares-Authelia-Header X-Bfl-User. Wir mappen den Olares-
-- Username auf eine interne UUID in unserer users-Tabelle.
-- ========================================================================

-- Extensions
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";
create extension if not exists "vector";
create extension if not exists "pg_trgm";

-- ========================================================================
-- USERS (Mapping zwischen Olares-Username und interner UUID)
-- ========================================================================

create table public.users (
  id              uuid primary key default uuid_generate_v4(),
  olares_username text not null unique,         -- aus X-Bfl-User Header
  email           text,
  display_name    text,
  created_at      timestamptz not null default now(),
  last_seen_at    timestamptz not null default now(),
  deleted_at      timestamptz
);

create index users_olares_idx on public.users (olares_username) where deleted_at is null;

-- ========================================================================
-- ORGANIZATIONS (Mandanten)
-- ========================================================================

create table public.orgs (
  id              uuid primary key default uuid_generate_v4(),
  name            text not null,
  slug            text unique not null,
  industry        text,                                  -- "law", "tax", "consulting", "industry"
  settings        jsonb not null default '{}'::jsonb,
  audio_retention_days integer not null default 90,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz
);

create index orgs_slug_idx on public.orgs (slug) where deleted_at is null;

-- ========================================================================
-- USER ↔ ORG MAPPING (Multi-Tenancy)
-- ========================================================================

create type public.user_role as enum ('owner', 'admin', 'member', 'viewer');

create table public.user_org_roles (
  user_id         uuid not null references public.users(id) on delete cascade,
  org_id          uuid not null references public.orgs(id) on delete cascade,
  role            public.user_role not null default 'member',
  joined_at       timestamptz not null default now(),
  primary key (user_id, org_id)
);

create index user_org_roles_user_idx on public.user_org_roles (user_id);
create index user_org_roles_org_idx on public.user_org_roles (org_id);

-- ========================================================================
-- TEMPLATES
-- ========================================================================

create table public.templates (
  id              uuid primary key default uuid_generate_v4(),
  org_id          uuid references public.orgs(id) on delete cascade,
  name            text not null,
  description     text,
  category        text,
  system_prompt   text not null,
  output_schema   jsonb not null,
  is_system       boolean not null default false,
  is_active       boolean not null default true,
  version         integer not null default 1,
  created_by      uuid references public.users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index templates_org_idx on public.templates (org_id) where is_active = true;
create index templates_system_idx on public.templates (is_system) where is_active = true;

-- ========================================================================
-- MEETINGS
-- ========================================================================

create type public.meeting_status as enum (
  'draft',
  'uploading',
  'queued',
  'transcribing',
  'transcribed',
  'summarizing',
  'embedding',
  'ready',
  'failed',
  'archived'
);

create table public.meetings (
  id              uuid primary key default uuid_generate_v4(),
  org_id          uuid not null references public.orgs(id) on delete cascade,
  created_by      uuid not null references public.users(id),
  title           text not null default 'Unbenanntes Meeting',
  description     text,
  status          public.meeting_status not null default 'draft',
  recorded_at     timestamptz not null default now(),
  duration_sec    integer,
  audio_path      text,                                 -- Pfad in MinIO oder /app/data
  audio_size_bytes bigint,
  speaker_count   smallint,
  language        text default 'de',
  template_id     uuid references public.templates(id),
  metadata        jsonb not null default '{}'::jsonb,
  error_message   text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz
);

create index meetings_org_idx on public.meetings (org_id) where deleted_at is null;
create index meetings_status_idx on public.meetings (status) where deleted_at is null;
create index meetings_recorded_idx on public.meetings (recorded_at desc) where deleted_at is null;
create index meetings_title_trgm on public.meetings using gin (title gin_trgm_ops);

-- ========================================================================
-- TRANSCRIPTS
-- ========================================================================

create table public.transcripts (
  id              uuid primary key default uuid_generate_v4(),
  meeting_id      uuid not null unique references public.meetings(id) on delete cascade,
  segments        jsonb not null,
  speakers        jsonb not null default '[]'::jsonb,
  full_text       text not null,
  language        text not null default 'de',
  whisper_model   text not null,
  diarization_model text,
  word_count      integer,
  created_at      timestamptz not null default now()
);

create index transcripts_fulltext_idx on public.transcripts using gin (to_tsvector('german', full_text));

-- ========================================================================
-- SUMMARIES
-- ========================================================================

create table public.summaries (
  id              uuid primary key default uuid_generate_v4(),
  meeting_id      uuid not null references public.meetings(id) on delete cascade,
  template_id     uuid not null references public.templates(id),
  template_version integer not null,
  content         jsonb not null,
  llm_model       text not null,
  generation_time_ms integer,
  is_current      boolean not null default true,
  created_at      timestamptz not null default now()
);

create index summaries_meeting_idx on public.summaries (meeting_id) where is_current = true;

-- ========================================================================
-- MEETING CHUNKS (für RAG)
-- ========================================================================

create table public.meeting_chunks (
  id              uuid primary key default uuid_generate_v4(),
  meeting_id      uuid not null references public.meetings(id) on delete cascade,
  chunk_index     integer not null,
  content         text not null,
  start_time_sec  integer,
  end_time_sec    integer,
  speaker_ids     text[],
  embedding       vector(1024),
  token_count     integer,
  created_at      timestamptz not null default now()
);

create index meeting_chunks_meeting_idx on public.meeting_chunks (meeting_id);
create index meeting_chunks_embedding_idx on public.meeting_chunks
  using hnsw (embedding vector_cosine_ops);

-- ========================================================================
-- TAGS
-- ========================================================================

create table public.tags (
  id              uuid primary key default uuid_generate_v4(),
  org_id          uuid not null references public.orgs(id) on delete cascade,
  name            text not null,
  color           text default '#737065',
  created_at      timestamptz not null default now(),
  unique (org_id, name)
);

create table public.meeting_tags (
  meeting_id      uuid not null references public.meetings(id) on delete cascade,
  tag_id          uuid not null references public.tags(id) on delete cascade,
  added_at        timestamptz not null default now(),
  primary key (meeting_id, tag_id)
);

-- ========================================================================
-- AUDIT LOG
-- ========================================================================

create table public.audit_log (
  id              uuid primary key default uuid_generate_v4(),
  timestamp       timestamptz not null default now(),
  user_id         uuid references public.users(id),
  olares_user     text,                                -- aus X-Bfl-User
  org_id          uuid references public.orgs(id),
  action          text not null,
  resource_type   text,
  resource_id     uuid,
  ip_address      inet,
  user_agent      text,
  changes         jsonb,
  success         boolean not null default true,
  metadata        jsonb default '{}'::jsonb
);

create index audit_log_user_idx on public.audit_log (user_id, timestamp desc);
create index audit_log_org_idx on public.audit_log (org_id, timestamp desc);
create index audit_log_action_idx on public.audit_log (action, timestamp desc);
create index audit_log_resource_idx on public.audit_log (resource_type, resource_id);

-- ========================================================================
-- UPDATED_AT TRIGGER
-- ========================================================================

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger orgs_updated_at before update on public.orgs
  for each row execute procedure public.set_updated_at();

create trigger meetings_updated_at before update on public.meetings
  for each row execute procedure public.set_updated_at();

create trigger templates_updated_at before update on public.templates
  for each row execute procedure public.set_updated_at();
