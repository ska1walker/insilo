-- ========================================================================
-- 0014_webhook_request_bytes.sql
-- Gesendete Nutzlast pro Webhook-Zustellung messbar machen.
--
-- Hintergrund:
--   Der Datenschutz-Nachweis in der Navigation soll zeigen, was die Box
--   tatsächlich verlassen hat — das AImighty-Designsystem verlangt dafür
--   ausdrücklich gemessene Werte ("mit gemessenen Werten — oder gar
--   nicht"). `webhook_deliveries` protokollierte bisher nur die ANTWORT
--   (`response_body`, erste 512 Zeichen), nicht die Größe dessen, was wir
--   selbst hinausgeschickt haben.
--
--   `request_bytes` hält die Länge des signierten JSON-Body in Bytes, so
--   wie er über die Leitung ging. NULL bedeutet "vor dieser Migration
--   zugestellt, Größe unbekannt" — davon zu unterscheiden ist 0, das es
--   praktisch nicht gibt, weil jeder Payload einen Rumpf hat.
--
-- Bewusst keine Speicherung des Payloads selbst: für den Nachweis genügt
-- die Größe, und ein zweites Abbild der Besprechungsinhalte im Audit-Log
-- wäre genau die Datensammlung, die Insilo vermeidet.
--
-- Idempotent (IF NOT EXISTS), wie jede Migration hier — der Init-Container
-- versucht bei jedem Start alle Dateien erneut (siehe HANDOFF v0.1.51).
-- ========================================================================

alter table public.webhook_deliveries
  add column if not exists request_bytes int;

comment on column public.webhook_deliveries.request_bytes is
  'Größe des gesendeten JSON-Body in Bytes. NULL = vor Migration 0014 zugestellt.';
