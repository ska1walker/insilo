-- ============================================================================
-- 0015 — Speech-to-Text als konfigurierbarer Endpunkt
--
-- Bis hierher war die Spracherkennung fest verdrahtet: der mitgelieferte
-- Whisper-Dienst im eigenen Namespace. Damit galt "kein Audio verlässt die
-- Box" ohne Ausnahme.
--
-- Ab jetzt lässt sich stattdessen ein OpenAI-kompatibler STT-Server
-- eintragen (z. B. eine Speaches-Instanz auf derselben Box). Leer heißt
-- weiterhin: der mitgelieferte Dienst übernimmt. Genau wie beim
-- Sprachmodell gibt es **keinen Vorgabewert** — jede geratene Adresse wäre
-- beim nächsten Kunden falsch.
--
-- Folge für den Datenschutz-Nachweis: Audio wird zum möglichen Ziel und
-- muss dort benannt werden. Siehe backend/app/routers/egress.py.
-- ============================================================================

alter table public.org_settings
  add column if not exists stt_base_url text not null default '',
  add column if not exists stt_api_key  text not null default '',
  add column if not exists stt_model    text not null default '';

comment on column public.org_settings.stt_base_url is
  'OpenAI-kompatibler STT-Endpunkt. Leer = mitgelieferter Whisper-Dienst.';
comment on column public.org_settings.stt_model is
  'Modellkennung beim Endpunkt, z. B. Systran/faster-whisper-large-v3.';
