-- ============================================================================
-- 0020 — Fertig erkannte Abschnitte einer langen Aufnahme
--
-- Seit 0.1.99 zerlegt der Worker eine lange Aufnahme in Abschnitte und
-- schickt jeden einzeln zur Spracherkennung (`app/audiostuecke.py`). Ohne
-- diese Tabelle wäre damit nur die eine Sache gewonnen, dass kein
-- einzelner Aufruf mehr in ein Zeitlimit läuft — bricht der Lauf beim
-- siebten von zwölf Abschnitten ab, begänne der nächste Versuch wieder
-- bei eins, und auf dem langsamen Weg kostet das eine Stunde.
--
-- Hier liegt deshalb jeder fertige Abschnitt, bis die Besprechung
-- vollständig ist. Danach wird er gelöscht: der Inhalt steht dann in
-- `transcripts`, und zwei Quellen für denselben Wortlaut wären eine zu
-- viel. Die Zeilen sind also Zwischenstand, kein Bestand — sie gehören
-- weder in eine Sicherung noch in die externe Schnittstelle.
--
-- `start_sec`/`end_sec` sind die Grenzen in der **ganzen** Aufnahme, und
-- die Zeiten in `segments` sind bereits darauf umgerechnet. Wer die
-- Zeilen nach `idx` sortiert aneinanderhängt, hat das Transkript.
--
-- Der Init-Container führt jede Datei bei jedem Start aus — daher
-- durchgehend `if not exists` und `drop policy if exists`.
-- ============================================================================

create table if not exists public.transcription_chunks (
  meeting_id  uuid not null references public.meetings(id) on delete cascade,
  idx         integer not null,
  start_sec   double precision not null,
  end_sec     double precision not null,
  segments    jsonb not null default '[]'::jsonb,
  text        text not null default '',
  language    text,
  created_at  timestamptz not null default now(),
  primary key (meeting_id, idx)
);

comment on table public.transcription_chunks is
  'Zwischenstand der stückweisen Spracherkennung. Wird gelöscht, sobald '
  'das vollständige Transkript in public.transcripts steht.';

-- Zeilensicherheit wie bei jeder anderen Tabelle (siehe 0017). Ohne die
-- erzwungene Variante käme der Tabelleneigentümer an allen Regeln vorbei.
alter table public.transcription_chunks enable row level security;
alter table public.transcription_chunks force row level security;

-- Die Hintergrundaufgaben, die hier schreiben. Sie laufen ohne
-- angemeldeten Nutzer und weisen sich über `public.ist_dienst()` aus.
drop policy if exists transcription_chunks_dienst on public.transcription_chunks;
create policy transcription_chunks_dienst on public.transcription_chunks
  for all
  using (public.ist_dienst())
  with check (public.ist_dienst());

-- Lesen darf, wer die Besprechung sehen darf — dafür, dass die
-- Oberfläche den Fortschritt anzeigen kann. Schreiben ausdrücklich
-- nicht: der Wortlaut entsteht ausschließlich im Worker.
drop policy if exists transcription_chunks_select on public.transcription_chunks;
create policy transcription_chunks_select on public.transcription_chunks
  for select
  using (
    meeting_id in (
      select id from public.meetings
      where org_id in (select public.current_user_orgs())
    )
  );

-- Bewusst **keine** Regel für `api_schluessel_org()`: die externe
-- Schnittstelle liefert fertige Besprechungen aus, keinen Zwischenstand.
