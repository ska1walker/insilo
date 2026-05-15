-- ========================================================================
-- 0011_ui_locale.sql
-- UI-Locale-Settings für i18n (v0.1.43+). Resolution-Hierarchie:
--   user.ui_locale > org_settings.ui_locale > Browser Accept-Language > 'de'
--
-- Beide Spalten sind nullable: null bedeutet "kein Override an dieser
-- Stelle, gehe zur nächsten Resolution-Stufe". So bleibt jede existing
-- Org per Default deutsch ohne Migration-Backfill.
-- ========================================================================

alter table public.org_settings
  add column if not exists ui_locale text;

alter table public.users
  add column if not exists ui_locale text;

-- CHECK-Constraints: nur die fünf von uns unterstützten Sprachen.
-- 'de' = Deutsch, 'en' = Englisch, 'fr' = Französisch,
-- 'es' = Spanisch, 'it' = Italienisch.
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'org_settings_ui_locale_valid'
  ) then
    alter table public.org_settings
      add constraint org_settings_ui_locale_valid
      check (ui_locale is null or ui_locale in ('de', 'en', 'fr', 'es', 'it'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'users_ui_locale_valid'
  ) then
    alter table public.users
      add constraint users_ui_locale_valid
      check (ui_locale is null or ui_locale in ('de', 'en', 'fr', 'es', 'it'));
  end if;
end$$;
