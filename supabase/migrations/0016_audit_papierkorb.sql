-- ========================================================================
-- 0016 — Protokoll und Papierkorb
--
-- Zwei Versprechen aus CLAUDE.md, die bis hierher nur als Absicht
-- existierten:
--
--   „Audit-Trail. Jede Datenänderung wird geloggt."
--   „Reversibilität. Soft-Delete + 30-Tage-Frist vor Hard-Delete."
--
-- `public.audit_log` liegt seit 0001 samt Indizes und RLS bereit, aber
-- kein Code hat je hineingeschrieben. Und das Löschen setzte zwar
-- `deleted_at`, entfernte die Tonaufnahme aber sofort und unwiderruflich —
-- die Frist galt für die Datenbankzeile, nicht für die Datei.
--
-- Diese Migration ergänzt, was dafür fehlt. Sie ist idempotent
-- (Lesson aus 0012, siehe HANDOFF v0.1.51).
-- ========================================================================

-- ── Protokoll: auch Aufrufe über einen Zugriffsschlüssel haben einen Urheber ──
--
-- Die externe Schnittstelle authentifiziert nicht über X-Bfl-User, sondern
-- über einen Zugriffsschlüssel. Ohne diese Spalte wäre genau der Weg, auf
-- dem Daten die Box verlassen, der einzige ohne benennbaren Urheber.
alter table public.audit_log
  add column if not exists api_key_id uuid references public.api_keys(id) on delete set null;

create index if not exists audit_log_api_key_idx
  on public.audit_log (api_key_id, timestamp desc);

-- Append-only war bisher nur durch Weglassen erzwungen: 0002 verbietet
-- update und delete, erlaubt aber nirgends ausdrücklich das Einfügen. Das
-- trägt, solange die Anwendung als Eigentümerin der Tabelle verbindet
-- (Eigentümer umgehen RLS). Diese Regel schreibt die Absicht hin, damit
-- das Protokoll auch dann noch schreibbar ist, wenn jemand später
-- `force row level security` setzt.
drop policy if exists audit_log_insert on public.audit_log;
create policy audit_log_insert on public.audit_log
  for insert
  with check (true);

-- ── Papierkorb: Frist pro Organisation ──────────────────────────────────
--
-- Neben `audio_retention_days` (seit 0001, bis hierher von niemandem
-- gelesen). Beide Fristen setzt jetzt `app/tasks/aufraeumen.py` durch.
alter table public.orgs
  add column if not exists trash_retention_days integer not null default 30;

comment on column public.orgs.trash_retention_days is
  'Tage zwischen Löschen und endgültigem Entfernen. 0 = sofort endgültig.';

comment on column public.orgs.audio_retention_days is
  'Tage, die eine Tonaufnahme aufbewahrt wird. Danach entfällt die Datei, '
  'Transkript und Zusammenfassung bleiben. 0 = unbegrenzt.';

-- ── Besprechungen: die Tonaufnahme kann vor der Besprechung gehen ───────
--
-- Die Aufbewahrungsfrist trifft die Aufnahme, nicht das Protokoll: nach
-- Ablauf verschwindet die Datei, das Transkript bleibt lesbar. Damit die
-- Oberfläche „Aufnahme nach Frist entfernt" von „nie hochgeladen"
-- unterscheiden kann, wird der Zeitpunkt festgehalten.
alter table public.meetings
  add column if not exists audio_deleted_at timestamptz;

-- Der Papierkorb fragt genau andersherum als jede andere Ansicht: nur
-- gelöschte Zeilen. Die vorhandenen Indizes sind partiell auf
-- `deleted_at is null` — für diese Abfrage also nutzlos.
create index if not exists meetings_papierkorb_idx
  on public.meetings (org_id, deleted_at desc)
  where deleted_at is not null;

-- Der Aufräum-Job sucht Aufnahmen, deren Frist abgelaufen ist.
create index if not exists meetings_audio_frist_idx
  on public.meetings (org_id, recorded_at)
  where audio_path is not null and audio_deleted_at is null;
