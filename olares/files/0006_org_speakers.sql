-- ========================================================================
-- 0006_org_speakers.sql
-- Org-scoped speaker catalog with biometric voiceprints (ECAPA-TDNN, 192-d).
--
-- Drei Tabellen:
--   org_speakers              — was der User sieht (Name + 1 Voiceprint)
--   speaker_voiceprints       — Audit-Trail aller Samples (löschbar pro Sample)
--   meeting_speaker_clusters  — Verbindung Meeting↔Cluster↔Speaker
--
-- Cosine-Similarity-Matching gegen die L2-normalisierten ECAPA-Embeddings
-- aus dem Whisper-Service. Voiceprints sind biometrische Daten — sie
-- verlassen die Olares-Box nie und sind via RLS strikt org-isoliert.
-- ========================================================================

-- ─── Globaler Org-Roster ───────────────────────────────────────────────

create table if not exists public.org_speakers (
  id            uuid primary key default uuid_generate_v4(),
  org_id        uuid not null references public.orgs(id) on delete cascade,
  display_name  text not null,
  description   text not null default '',
  -- "Das bin ich"-Marker. Höchstens einer pro Org. Fließt ins LLM-Prompt:
  -- die Summary darf den Self-Speaker in zweiter Person formulieren.
  is_self       boolean not null default false,
  created_at    timestamptz not null default now(),
  created_by    uuid references public.users(id),
  -- Primärer Voiceprint = laufender Mittelwert aller Samples,
  -- L2-normalisiert. null wenn Sprecher per Hand angelegt wurde ohne
  -- je gesprochen zu haben — Auto-Match überspringt solche Zeilen.
  voiceprint    vector(192),
  sample_count  int  not null default 0,
  last_heard_at timestamptz,
  unique (org_id, display_name)
);

create index if not exists org_speakers_org_idx
  on public.org_speakers (org_id);

-- HNSW-Index für Cosine-Similarity. Bei <100 Sprechern technisch
-- nicht nötig, aber harmlos und zukunftssicher.
create index if not exists org_speakers_voiceprint_idx
  on public.org_speakers using hnsw (voiceprint vector_cosine_ops)
  where voiceprint is not null;

-- Höchstens ein is_self pro Org.
create unique index if not exists org_speakers_is_self_idx
  on public.org_speakers (org_id) where is_self = true;

-- ─── Append-only Sample-Sammlung ──────────────────────────────────────

create table if not exists public.speaker_voiceprints (
  id              uuid primary key default uuid_generate_v4(),
  org_speaker_id  uuid not null references public.org_speakers(id) on delete cascade,
  meeting_id      uuid not null references public.meetings(id) on delete cascade,
  cluster_idx     int  not null,
  embedding       vector(192) not null,
  -- 'manual'    User hat den Cluster zugewiesen → Voiceprint gelernt
  -- 'auto-match' Auto-Match-Treffer (wird auch persistiert, damit der
  --              Voiceprint sich über Zeit verfeinert)
  -- 'reseed'    Re-Diarize-Knopf hat eine Stimme neu eingelesen
  source          text not null default 'manual',
  created_at      timestamptz not null default now(),
  created_by      uuid references public.users(id)
);

create index if not exists speaker_voiceprints_speaker_idx
  on public.speaker_voiceprints (org_speaker_id, created_at desc);

-- ─── Per-Meeting-Diarization-Cluster ──────────────────────────────────

create table if not exists public.meeting_speaker_clusters (
  id              uuid primary key default uuid_generate_v4(),
  meeting_id      uuid not null references public.meetings(id) on delete cascade,
  cluster_idx     int  not null,
  centroid        vector(192) not null,
  org_speaker_id  uuid references public.org_speakers(id) on delete set null,
  match_score     float,
  -- 'auto'    Centroid wurde via Threshold automatisch zugeordnet
  -- 'manual'  User hat den Cluster manuell zugewiesen
  -- 'pending' Cluster ist anonym geblieben (kein Match, kein Mapping)
  assignment      text not null default 'auto',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (meeting_id, cluster_idx)
);

create index if not exists meeting_speaker_clusters_meeting_idx
  on public.meeting_speaker_clusters (meeting_id);

-- updated_at-Trigger
drop trigger if exists meeting_speaker_clusters_updated_at on public.meeting_speaker_clusters;
create trigger meeting_speaker_clusters_updated_at
  before update on public.meeting_speaker_clusters
  for each row execute procedure public.set_updated_at();

-- ─── Row Level Security ────────────────────────────────────────────────

alter table public.org_speakers              enable row level security;
alter table public.speaker_voiceprints       enable row level security;
alter table public.meeting_speaker_clusters  enable row level security;

drop policy if exists org_speakers_select on public.org_speakers;
create policy org_speakers_select on public.org_speakers
  for select
  using (org_id in (select public.current_user_orgs()));

drop policy if exists org_speakers_modify on public.org_speakers;
create policy org_speakers_modify on public.org_speakers
  for all
  using (org_id in (select public.current_user_orgs()))
  with check (org_id in (select public.current_user_orgs()));

drop policy if exists speaker_voiceprints_select on public.speaker_voiceprints;
create policy speaker_voiceprints_select on public.speaker_voiceprints
  for select
  using (
    org_speaker_id in (
      select id from public.org_speakers
      where org_id in (select public.current_user_orgs())
    )
  );

drop policy if exists speaker_voiceprints_modify on public.speaker_voiceprints;
create policy speaker_voiceprints_modify on public.speaker_voiceprints
  for all
  using (
    org_speaker_id in (
      select id from public.org_speakers
      where org_id in (select public.current_user_orgs())
    )
  )
  with check (
    org_speaker_id in (
      select id from public.org_speakers
      where org_id in (select public.current_user_orgs())
    )
  );

drop policy if exists meeting_speaker_clusters_select on public.meeting_speaker_clusters;
create policy meeting_speaker_clusters_select on public.meeting_speaker_clusters
  for select
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
        and deleted_at is null
    )
  );

drop policy if exists meeting_speaker_clusters_modify on public.meeting_speaker_clusters;
create policy meeting_speaker_clusters_modify on public.meeting_speaker_clusters
  for all
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
    )
  )
  with check (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
    )
  );
