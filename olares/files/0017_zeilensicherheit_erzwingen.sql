-- ========================================================================
-- 0017 — Zeilensicherheit erzwingen
--
-- Migration 0002 hat die Regeln geschrieben. Wirksam waren sie nie:
--
--   1. Der Kontext, den sie lesen (`app.current_user_id`), wurde von
--      keiner Zeile Code gesetzt — im Backend gab es weder `set_config`
--      noch einen Aufruf von `current_user_id()`.
--   2. Überall stand nur `enable row level security`, nie `force`. Das
--      Backend verbindet als **Eigentümerin** der Tabellen, und die
--      umgeht RLS ohne `force` grundsätzlich.
--
-- Getrennt wurden die Mandanten damit allein durch `where org_id = $1`
-- in jeder einzelnen Abfrage — eine Zusicherung, die an der Sorgfalt
-- jedes künftigen Endpunkts hängt. Diese Migration macht die Regeln
-- wirksam; der Filter in den Abfragen bleibt daneben stehen.
--
-- `users`, `orgs` und `user_org_roles` bleiben ausgenommen: die
-- Erstanlage einer Identität muss durchkommen, bevor es einen Kontext
-- gibt, den die Regeln lesen könnten.
--
-- Idempotent (Lesson aus 0012, siehe HANDOFF v0.1.51).
-- ========================================================================

-- ── Zwei Kontexte neben dem Nutzer ──────────────────────────────────────

-- Hintergrunddienste. Transkription, Zusammenfassung, Einbettung,
-- Webhook-Versand, Aufräumlauf und der Konfigurations-Abzug laufen ohne
-- angemeldeten Nutzer; ohne diese Ausnahme sähen sie keine Zeile und
-- könnten keine schreiben.
--
-- Gesetzt wird der Wert ausschließlich in `app/db.py` von Prozessen, die
-- ohnehin die Zugangsdaten der Datenbank haben. Aus einer HTTP-Anfrage
-- ist er nicht erreichbar: er kommt nicht aus Kopfzeilen oder Rumpf,
-- sondern aus dem Code, der die Verbindung aufmacht.
create or replace function public.ist_dienst()
returns boolean
language sql
stable
as $$
  select coalesce(nullif(current_setting('app.dienst', true), ''), '0') = '1';
$$;

-- Die externe Schnittstelle weist sich mit einem Zugriffsschlüssel aus,
-- nicht mit einer Olares-Identität. Sie bekommt genau eine Organisation
-- und ausschließlich Leserechte.
create or replace function public.api_schluessel_org()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('app.api_key_org', true), '')::uuid;
$$;

-- ── Zwei Lücken in 0002, die vor dem Erzwingen zu schließen sind ────────

-- 1. `meetings_select` verlangte `deleted_at is null`. Damit wäre der
--    Papierkorb (0016) leer und das endgültige Löschen fände seine Zeile
--    nicht. Die Bedingung entfällt hier; jede Ansicht außer dem
--    Papierkorb filtert ohnehin selbst darauf — nachgeprüft in
--    meetings.py, search.py und external_api.py.
drop policy if exists meetings_select on public.meetings;
create policy meetings_select on public.meetings
  for select
  using (org_id in (select public.current_user_orgs()));

-- 2. Für `templates` gab es keine Lösch-Regel — `delete_template` wäre
--    unter `force` ins Leere gelaufen. Dieselbe Bedingung wie beim
--    Ändern: eigene Organisation, Verwaltung, keine Werksvorlage.
drop policy if exists templates_delete on public.templates;
create policy templates_delete on public.templates
  for delete
  using (
    org_id in (select public.current_user_orgs())
    and public.current_user_role_in_org(org_id) in ('owner', 'admin')
    and is_system = false
  );

-- ── Dienst-Ausnahme je Tabelle ──────────────────────────────────────────
--
-- Permissive Regeln werden mit ODER verknüpft: die Ausnahme steht neben
-- den Nutzerregeln aus 0002, sie ersetzt keine.
do $$
declare t text;
begin
  foreach t in array array[
    'meetings', 'transcripts', 'summaries', 'meeting_chunks',
    'templates', 'tags', 'meeting_tags', 'audit_log',
    'org_settings', 'template_customizations',
    'org_webhooks', 'webhook_deliveries', 'api_keys',
    'org_speakers', 'speaker_voiceprints', 'meeting_speaker_clusters'
  ]
  loop
    execute format('drop policy if exists %I on public.%I', t || '_dienst', t);
    execute format(
      'create policy %I on public.%I for all using (public.ist_dienst()) with check (public.ist_dienst())',
      t || '_dienst', t
    );
  end loop;
end $$;

-- ── Lesezugang für die externe Schnittstelle ────────────────────────────
--
-- Nur die Tabellen, die `/api/external/v1/*` tatsächlich liest, und nur
-- `for select`. Schreiben ist über diesen Kontext nirgends möglich.
drop policy if exists meetings_api_schluessel on public.meetings;
create policy meetings_api_schluessel on public.meetings
  for select using (org_id = public.api_schluessel_org());

drop policy if exists transcripts_api_schluessel on public.transcripts;
create policy transcripts_api_schluessel on public.transcripts
  for select using (
    meeting_id in (select id from public.meetings where org_id = public.api_schluessel_org())
  );

drop policy if exists summaries_api_schluessel on public.summaries;
create policy summaries_api_schluessel on public.summaries
  for select using (
    meeting_id in (select id from public.meetings where org_id = public.api_schluessel_org())
  );

drop policy if exists tags_api_schluessel on public.tags;
create policy tags_api_schluessel on public.tags
  for select using (org_id = public.api_schluessel_org());

drop policy if exists meeting_tags_api_schluessel on public.meeting_tags;
create policy meeting_tags_api_schluessel on public.meeting_tags
  for select using (
    meeting_id in (select id from public.meetings where org_id = public.api_schluessel_org())
  );

-- Werksvorlagen tragen keine Organisation; die externe Ansicht nennt nur
-- den Namen der verwendeten Vorlage.
drop policy if exists templates_api_schluessel on public.templates;
create policy templates_api_schluessel on public.templates
  for select using (
    public.api_schluessel_org() is not null
    and (is_system = true or org_id = public.api_schluessel_org())
  );

-- ── Und jetzt erzwingen ─────────────────────────────────────────────────
--
-- `force` gilt auch für die Eigentümerin der Tabellen — also für genau
-- die Verbindung, mit der Insilo arbeitet. Ohne diese Zeilen ist alles
-- darüber Zierde.
--
-- Bewusst NICHT dabei: users, orgs, user_org_roles. Die Anmeldung löst
-- die Identität auf, bevor es einen Kontext gibt; würden sie mitgezwungen,
-- käme keine erste Anmeldung mehr durch.
do $$
declare t text;
begin
  foreach t in array array[
    'meetings', 'transcripts', 'summaries', 'meeting_chunks',
    'templates', 'tags', 'meeting_tags', 'audit_log',
    'org_settings', 'template_customizations',
    'org_webhooks', 'webhook_deliveries', 'api_keys',
    'org_speakers', 'speaker_voiceprints', 'meeting_speaker_clusters'
  ]
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
  end loop;
end $$;
