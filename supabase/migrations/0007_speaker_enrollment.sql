-- ========================================================================
-- 0007_speaker_enrollment.sql
-- Allow standalone voiceprint enrollments (no associated meeting).
--
-- v0.1.37's `speaker_voiceprints.meeting_id` was NOT NULL because every
-- sample came from a meeting cluster. v0.1.38 introduces the dedicated
-- "Stimmprobe abgeben"-Flow (user reads "Der Nordwind und die Sonne"),
-- where there is no meeting attached. We relax the column to nullable
-- and tag those rows with `source='enrollment'`.
-- ========================================================================

alter table public.speaker_voiceprints
  alter column meeting_id drop not null;

alter table public.speaker_voiceprints
  alter column cluster_idx drop not null;

-- Index to find enrollment samples fast (no meeting_id).
create index if not exists speaker_voiceprints_enrollment_idx
  on public.speaker_voiceprints (org_speaker_id)
  where meeting_id is null;
