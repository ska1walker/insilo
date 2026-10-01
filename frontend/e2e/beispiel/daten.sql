-- Beispieldaten für den Rundgang im Browser (e2e/, CI-Job „oberfläche“).
-- Setzt voraus, dass der Nutzer "devuser"
-- samt Organisation existiert (einmal GET /api/v1/meetings mit X-Bfl-User).
select set_config('app.dienst', '1', false);

do $$
declare
  v_org  uuid := (select org_id from public.user_org_roles r join public.users u on u.id = r.user_id where u.olares_username = 'devuser' limit 1);
  v_user uuid := (select id from public.users where olares_username = 'devuser');
  m1 uuid := '11111111-1111-4111-8111-000000000001';
  m2 uuid := '11111111-1111-4111-8111-000000000002';
  m3 uuid := '11111111-1111-4111-8111-000000000003';
  m4 uuid := '11111111-1111-4111-8111-000000000004';
  sp_alb uuid := '22222222-2222-4222-8222-000000000001';
  sp_mer uuid := '22222222-2222-4222-8222-000000000002';
begin
  update public.orgs set name = 'Kanzlei Albers & Partner' where id = v_org;
  update public.users set display_name = 'Jonas Albers' where id = v_user;

  insert into public.org_settings (org_id, llm_base_url, llm_model, updated_by)
  values (v_org, 'http://litellm.beispiel.olares.local/v1', 'qwen2.5-14b-instruct', v_user)
  on conflict (org_id) do update set llm_base_url = excluded.llm_base_url, llm_model = excluded.llm_model;

  insert into public.org_speakers (id, org_id, display_name, description, is_self, created_by, sample_count, last_heard_at)
  values (sp_alb, v_org, 'Jonas Albers', 'Partner, Steuerrecht', true, v_user, 3, now() - interval '1 day'),
         (sp_mer, v_org, 'Dr. Merle Hansen', 'Mandantin, Hansen Logistik GmbH', false, v_user, 1, now() - interval '1 day')
  on conflict (id) do nothing;

  -- 1: Mandantengespräch, fertig
  insert into public.meetings (id, org_id, created_by, title, status, recorded_at, duration_sec, audio_path, audio_size_bytes, speaker_count, language, template_id, metadata, created_at)
  values (m1, v_org, v_user, 'Mandantengespräch Hansen Logistik — Umstrukturierung 2027', 'ready',
          now() - interval '1 day 3 hours', 1260, v_org || '/' || m1 || '.wav', 10080044, 2, 'de',
          '00000000-0000-0000-0000-000000000002', '{"mime_type":"audio/wav"}', now() - interval '1 day 3 hours')
  on conflict (id) do nothing;

  insert into public.transcripts (meeting_id, segments, speakers, full_text, language, whisper_model, word_count)
  values (m1,
  jsonb_build_array(
    jsonb_build_object('start',0.0,'end',9.4,'speaker','org_'||sp_alb,'text','Guten Morgen, Frau Dr. Hansen. Schön, dass wir das heute persönlich besprechen können.'),
    jsonb_build_object('start',9.4,'end',24.8,'speaker','org_'||sp_mer,'text','Guten Morgen. Ja, uns drängt die Zeit ein wenig. Der Gesellschafterbeschluss soll im Januar fallen, und ich möchte vorher wissen, ob die Ausgliederung der Lagerhalle steuerneutral möglich ist.'),
    jsonb_build_object('start',24.8,'end',51.2,'speaker','org_'||sp_alb,'text','Das hängt im Wesentlichen davon ab, ob die Halle ein Teilbetrieb im Sinne des Umwandlungssteuergesetzes ist. Nach dem, was Sie mir geschickt haben, spricht einiges dafür — eigenes Personal, eigene Kostenstelle, eigene Kunden.'),
    jsonb_build_object('start',51.2,'end',68.0,'speaker','org_'||sp_mer,'text','Die Kunden sind teilweise dieselben wie im Speditionsgeschäft. Ist das ein Problem?'),
    jsonb_build_object('start',68.0,'end',97.5,'speaker','org_'||sp_alb,'text','Nicht zwingend, aber wir sollten es sauber dokumentieren. Ich schlage vor, dass wir eine verbindliche Auskunft beim Finanzamt beantragen. Das kostet etwas Zeit, gibt Ihnen aber Sicherheit für den Beschluss.'),
    jsonb_build_object('start',97.5,'end',112.3,'speaker','org_'||sp_mer,'text','Wie lange dauert so eine Auskunft in der Regel?'),
    jsonb_build_object('start',112.3,'end',139.0,'speaker','org_'||sp_alb,'text','Erfahrungsgemäß drei bis sechs Monate. Wenn wir den Antrag bis Ende Oktober stellen, ist ein Bescheid vor dem Beschluss realistisch, aber nicht garantiert.'),
    jsonb_build_object('start',139.0,'end',160.4,'speaker','org_'||sp_mer,'text','Gut. Dann machen wir das so. Ich schicke Ihnen bis Freitag die Mietverträge und die Personalliste der Halle.'),
    jsonb_build_object('start',160.4,'end',181.9,'speaker','org_'||sp_alb,'text','Sehr gut. Ich bereite parallel den Entwurf des Antrags vor und schicke ihn Ihnen in zwei Wochen zur Durchsicht.')
  ),
  jsonb_build_array(
    jsonb_build_object('id','org_'||sp_alb,'name','Jonas Albers','org_speaker_id',sp_alb,'match_score',0.91,'assignment','auto'),
    jsonb_build_object('id','org_'||sp_mer,'name','Dr. Merle Hansen','org_speaker_id',sp_mer,'match_score',0.84,'assignment','manual')
  ),
  'Guten Morgen, Frau Dr. Hansen. … Ausgliederung der Lagerhalle steuerneutral … verbindliche Auskunft beim Finanzamt …',
  'de', 'large-v3', 214)
  on conflict (meeting_id) do nothing;

  insert into public.summaries (meeting_id, template_id, template_version, content, llm_model, generation_time_ms)
  values (m1, '00000000-0000-0000-0000-000000000002', 1, jsonb_build_object(
    '_analyse', 'Erstgespräch zur geplanten Ausgliederung; Fokus auf steuerliche Neutralität.',
    'kurzfassung', 'Die Ausgliederung der Lagerhalle soll steuerneutral erfolgen. Ob die Halle ein Teilbetrieb ist, wird über eine verbindliche Auskunft beim Finanzamt abgesichert; der Antrag geht bis Ende Oktober raus. Der Gesellschafterbeschluss im Januar hängt vom Bescheid ab.',
    'mandant', 'Hansen Logistik GmbH, vertreten durch Dr. Merle Hansen',
    'sachverhalt', 'Die Lagerhalle soll aus der Spedition in eine eigene GmbH ausgegliedert werden. Sie hat eigenes Personal und eine eigene Kostenstelle; ein Teil der Kunden überschneidet sich mit dem Speditionsgeschäft.',
    'vereinbarte_leistungen', jsonb_build_array('Antrag auf verbindliche Auskunft vorbereiten und stellen', 'Teilbetriebseigenschaft dokumentieren'),
    'naechste_schritte_mandat', jsonb_build_array('Mandantin schickt Mietverträge und Personalliste bis Freitag', 'Kanzlei schickt Antragsentwurf in zwei Wochen', 'Antrag bis 31. Oktober beim Finanzamt einreichen'),
    'offene_fragen', jsonb_build_array('Wie werden gemeinsame Kunden zwischen Halle und Spedition aufgeteilt?')
  ), 'qwen2.5-14b-instruct', 41230);

  -- 2: Allgemeine Besprechung, fertig
  insert into public.meetings (id, org_id, created_by, title, status, recorded_at, duration_sec, audio_path, audio_size_bytes, speaker_count, language, template_id, metadata, created_at)
  values (m2, v_org, v_user, 'Teamrunde Steuerabteilung KW 40', 'ready',
          now() - interval '3 hours', 840, v_org || '/' || m2 || '.wav', 6720044, 3, 'de',
          '00000000-0000-0000-0000-000000000001', '{"mime_type":"audio/wav"}', now() - interval '3 hours')
  on conflict (id) do nothing;

  insert into public.transcripts (meeting_id, segments, speakers, full_text, language, whisper_model, word_count)
  values (m2,
  jsonb_build_array(
    jsonb_build_object('start',0.0,'end',12.1,'speaker','org_'||sp_alb,'text','Dann fangen wir an. Erster Punkt: die Fristen für die Jahresabschlüsse im vierten Quartal.'),
    jsonb_build_object('start',12.1,'end',30.6,'speaker','cluster_1','text','Wir haben noch elf Abschlüsse offen. Drei davon sind kritisch, weil die Belege fehlen. Ich habe die Mandanten letzte Woche erinnert.'),
    jsonb_build_object('start',30.6,'end',44.0,'speaker','cluster_2','text','Bei Schröder Bau habe ich gestern noch einmal angerufen. Die Unterlagen kommen Anfang nächster Woche.'),
    jsonb_build_object('start',44.0,'end',63.8,'speaker','org_'||sp_alb,'text','Gut. Zweiter Punkt: die neue E-Rechnungspflicht. Wir sollten bis Mitte November eine Mandanteninformation verschicken.'),
    jsonb_build_object('start',63.8,'end',80.2,'speaker','cluster_1','text','Ich kann den Entwurf übernehmen. Lisa, schaust du ihn dann gegen?'),
    jsonb_build_object('start',80.2,'end',88.0,'speaker','cluster_2','text','Ja, mache ich gern.')
  ),
  jsonb_build_array(
    jsonb_build_object('id','org_'||sp_alb,'name','Jonas Albers','org_speaker_id',sp_alb,'match_score',0.93,'assignment','auto'),
    jsonb_build_object('id','cluster_1','name','SPEAKER_01','match_score',0.41,'assignment','pending'),
    jsonb_build_object('id','cluster_2','name','SPEAKER_02','match_score',0.37,'assignment','pending')
  ),
  'Dann fangen wir an. Erster Punkt: die Fristen für die Jahresabschlüsse …',
  'de', 'large-v3', 112)
  on conflict (meeting_id) do nothing;

  insert into public.summaries (meeting_id, template_id, template_version, content, llm_model, generation_time_ms)
  values (m2, '00000000-0000-0000-0000-000000000001', 1, jsonb_build_object(
    '_analyse', 'Kurze Teamrunde mit zwei Punkten.',
    'kurzfassung', 'Elf Jahresabschlüsse sind offen, drei davon kritisch wegen fehlender Belege. Zur E-Rechnungspflicht geht bis Mitte November eine Mandanteninformation raus.',
    'anwesende', jsonb_build_array('Jonas Albers', 'SPEAKER_01', 'SPEAKER_02'),
    'kernthemen', jsonb_build_array('Fristen Jahresabschlüsse Q4', 'Mandanteninformation E-Rechnung'),
    'beschluesse', jsonb_build_array(
       jsonb_build_object('beschluss','Mandanteninformation zur E-Rechnung verschicken','verantwortlich','SPEAKER_01','frist','15.11.2026')),
    'naechste_schritte', jsonb_build_array('Entwurf Mandanteninformation schreiben', 'Gegenlesen durch Lisa', 'Unterlagen Schröder Bau nachhalten'),
    'offene_fragen', jsonb_build_array(),
    'wichtige_aussagen', jsonb_build_array(jsonb_build_object('sprecher','SPEAKER_01','aussage','Drei Abschlüsse sind kritisch, weil die Belege fehlen.'))
  ), 'qwen2.5-14b-instruct', 18750);

  -- 3: Vertriebsgespräch, Transkript da, Zusammenfassung läuft
  insert into public.meetings (id, org_id, created_by, title, status, recorded_at, duration_sec, audio_path, audio_size_bytes, speaker_count, language, template_id, metadata, created_at)
  values (m3, v_org, v_user, 'Erstgespräch Nordwerk Maschinenbau', 'summarizing',
          now() - interval '20 minutes', 600, v_org || '/' || m3 || '.wav', 4800044, 2, 'de',
          '00000000-0000-0000-0000-000000000003', '{"mime_type":"audio/wav"}', now() - interval '20 minutes')
  on conflict (id) do nothing;

  insert into public.transcripts (meeting_id, segments, speakers, full_text, language, whisper_model, word_count)
  values (m3,
  jsonb_build_array(
    jsonb_build_object('start',0.0,'end',14.0,'speaker','cluster_0','text','Wir suchen eine Kanzlei, die uns bei der Verrechnungspreisdokumentation für die Tochter in Polen unterstützt.'),
    jsonb_build_object('start',14.0,'end',31.5,'speaker','org_'||sp_alb,'text','Das machen wir regelmäßig. Wie groß ist das Volumen der konzerninternen Lieferungen ungefähr?')
  ),
  jsonb_build_array(
    jsonb_build_object('id','cluster_0','name','SPEAKER_00','match_score',0.2,'assignment','pending'),
    jsonb_build_object('id','org_'||sp_alb,'name','Jonas Albers','org_speaker_id',sp_alb,'match_score',0.9,'assignment','auto')
  ),
  'Wir suchen eine Kanzlei …', 'de', 'large-v3', 32)
  on conflict (meeting_id) do nothing;

  -- 4: im Papierkorb
  insert into public.meetings (id, org_id, created_by, title, status, recorded_at, duration_sec, speaker_count, language, template_id, created_at, deleted_at)
  values (m4, v_org, v_user, 'Testaufnahme Mikrofon Besprechungsraum 2', 'ready',
          now() - interval '6 days', 42, 1, 'de', '00000000-0000-0000-0000-000000000005', now() - interval '6 days', now() - interval '2 days')
  on conflict (id) do nothing;
end $$;
