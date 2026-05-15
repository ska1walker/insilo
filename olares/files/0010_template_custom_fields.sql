-- ========================================================================
-- 0010_template_custom_fields.sql
-- Lite-Schema-Editor (v0.1.41): org-spezifische Zusatzfelder pro Template.
--
-- Im Gegensatz zum vollen Schema-Editor (irgendwann v0.1.42+) erlauben
-- wir hier nur das *Hinzufügen* von Feldern — die fixen Felder der
-- System-Vorlagen bleiben unangetastet, damit Anzeige-Renderer und
-- existing Summaries weiter konsistent funktionieren. Eingriffe wie
-- "Umbenennen" oder "Löschen" bleiben Phase 2 vorbehalten.
--
-- Format der custom_fields-JSONB:
--   [
--     {"name": "geburtsdatum", "label": "Geburtsdatum",
--      "type": "string", "description": "Tag.Monat.Jahr falls genannt"},
--     {"name": "zeugen", "label": "Zeugen",
--      "type": "array_string", "description": "Namen der Zeugen"},
--     ...
--   ]
--
-- Erlaubte `type`-Werte (v0.1.41):
--   "string"        → einfaches Textfeld
--   "array_string"  → Liste von Texten
-- ========================================================================

alter table public.template_customizations
  add column if not exists custom_fields jsonb not null default '[]'::jsonb;
