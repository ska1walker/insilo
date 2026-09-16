-- ============================================================================
-- 0021 — Welche Besprechungen ein CRM übernimmt
--
-- Seit 0.1.93 schreibt Insilo jede fertige Zusammenfassung in den
-- gemeinsamen Ordner der Box, und Beacon liest ihn mit. Beacon hat damit
-- alles übernommen: interne Runden und Sprachnotizen ebenso wie
-- Kundengespräche. Die einzige Angabe, an der Beacon hätte filtern
-- können, war der Name der Vorlage — und der ist pro Organisation
-- umbenennbar (template_customizations.display_name) und bei eigenen
-- Vorlagen frei gewählt.
--
-- Die Frage, *wie* eine Besprechung zusammengefasst wird, und die Frage,
-- *wohin* das Ergebnis geht, sind zwei verschiedene. Deshalb steht die
-- zweite nicht in der Vorlage selbst, sondern daneben:
--
--   templates.an_crm         die Voreinstellung. Für Systemvorlagen setzt
--                            sie das Saatgut (Mandanten-, Vertriebs- und
--                            Jahresgespräch: ja; Allgemeine Besprechung
--                            und Schnellnotiz: nein), für eigene Vorlagen
--                            gilt nein.
--   template_weitergabe      was eine Organisation davon abweichend
--                            festlegt. Wirksam ist
--                            coalesce(template_weitergabe.an_crm,
--                                     templates.an_crm).
--
-- Eine eigene Tabelle und nicht eine Spalte in template_customizations:
-- dort macht jede Zeile eine Vorlage „angepasst", und „Zurücksetzen"
-- löscht die Zeile. Wer eine Vorlage aufs Standard-Prompt zurücksetzt,
-- soll nicht nebenbei ändern, was ins CRM geht.
--
-- Die Voreinstellung steht bewusst im Saatgut und nicht hier: diese Datei
-- läuft vor 0099_seed. Ein `update` hier träfe auf einer frischen
-- Installation keine Zeile, und die drei Kundengespräche stünden dort auf
-- nein.
--
-- Der Init-Container führt jede Datei bei jedem Start aus — daher
-- durchgehend `if not exists` und `drop policy if exists`.
-- ============================================================================

alter table public.templates
  add column if not exists an_crm boolean not null default false;

comment on column public.templates.an_crm is
  'Voreinstellung: übernimmt ein angeschlossenes CRM Besprechungen mit dieser '
  'Vorlage? Abweichungen je Organisation in public.template_weitergabe.';

create table if not exists public.template_weitergabe (
  org_id       uuid not null references public.orgs(id) on delete cascade,
  template_id  uuid not null references public.templates(id) on delete cascade,
  an_crm       boolean not null,
  updated_at   timestamptz not null default now(),
  updated_by   uuid references public.users(id),
  primary key (org_id, template_id)
);

comment on table public.template_weitergabe is
  'Abweichung einer Organisation von templates.an_crm. Wirksam ist '
  'coalesce(template_weitergabe.an_crm, templates.an_crm).';

alter table public.template_weitergabe enable row level security;
alter table public.template_weitergabe force row level security;

-- Lesen darf jedes Mitglied: die Oberfläche zeigt an jeder Vorlage, ob sie
-- weitergegeben wird.
drop policy if exists template_weitergabe_select on public.template_weitergabe;
create policy template_weitergabe_select on public.template_weitergabe
  for select
  using (org_id in (select public.current_user_orgs()));

-- Ändern nur Inhaber und Verwaltende. Das ist keine Frage der
-- Zusammenfassung, sondern eine, welche Gespräche eine andere App zu sehen
-- bekommt — dieselbe Grenze wie beim Nachziehen des Exports
-- (`meetings.export_backfill`). Das Backend prüft die Rolle vorher selbst
-- und antwortet mit 403; diese Regel ist der Boden darunter.
drop policy if exists template_weitergabe_schreiben on public.template_weitergabe;
create policy template_weitergabe_schreiben on public.template_weitergabe
  for all
  using (
    org_id in (select public.current_user_orgs())
    and public.current_user_role_in_org(org_id) in ('owner', 'admin')
  )
  with check (
    org_id in (select public.current_user_orgs())
    and public.current_user_role_in_org(org_id) in ('owner', 'admin')
  );

-- Die Hintergrundaufgaben lesen die Einstellung, wenn sie die Datei für
-- den gemeinsamen Ordner schreiben (siehe 0017).
drop policy if exists template_weitergabe_dienst on public.template_weitergabe;
create policy template_weitergabe_dienst on public.template_weitergabe
  for all
  using (public.ist_dienst())
  with check (public.ist_dienst());
