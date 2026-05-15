-- ========================================================================
-- 0008_manual_webhooks_template_overrides.sql
-- Three small, related quality-of-life changes for v0.1.39:
--
--   1. Webhooks gain a `trigger_mode` ('auto' | 'manual'). When set to
--      'manual', the meeting.ready event is NOT auto-dispatched — the
--      user has to explicitly click "An externe Systeme senden" on the
--      meeting detail. Other events (created/failed/updated/deleted)
--      keep their auto behaviour either way.
--
--      Existing webhooks are migrated to 'manual' retroactively so the
--      default is conservative (no surprise outbound traffic after
--      upgrade).
--
--   2. `template_customizations` gains `display_name` + `display_description`,
--      both NULL-able. When set, the org sees the customised name in
--      place of the system template's default (e.g. rename
--      "Mandantengespräch" → "Beratungstermin"). NULL means "use the
--      original".
--
--   3. No schema change for meetings — `meetings.title` is already
--      mutable. The corresponding PATCH endpoint lives in the backend.
-- ========================================================================

-- ─── Webhook trigger mode ──────────────────────────────────────────────

alter table public.org_webhooks
  add column if not exists trigger_mode text not null default 'manual'
    check (trigger_mode in ('auto', 'manual'));

-- Retroactively flip all existing webhooks to manual — caller-asked
-- behaviour ("safer default also for legacy rows").
update public.org_webhooks set trigger_mode = 'manual';

-- ─── Template name/description overrides ───────────────────────────────

alter table public.template_customizations
  add column if not exists display_name text;

alter table public.template_customizations
  add column if not exists display_description text;
