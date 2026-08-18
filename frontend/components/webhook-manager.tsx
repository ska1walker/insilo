"use client";

import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import {
  createWebhook,
  deleteWebhook,
  fetchDeliveries,
  fetchWebhooks,
  testWebhook,
  updateWebhook,
  WEBHOOK_EVENT_LABELS,
  WEBHOOK_EVENTS,
  type WebhookCreated,
  type WebhookDelivery,
  type WebhookEvent,
  type WebhookRead,
  type WebhookTestResult,
} from "@/lib/api/webhooks";

/**
 * CRUD + Test + Auslieferungs-Verlauf für ausgehende Webhooks.
 *
 * Webhook-Secrets werden vom Backend nur bei der Erstellung zurückgegeben —
 * die UI zeigt sie einmalig in einem One-Time-Reveal-Block und macht klar,
 * dass das Secret nicht erneut sichtbar sein wird.
 */
export function WebhookManager() {
  const t = useTranslations("webhookManager");
  const toast = useToast();
  const [webhooks, setWebhooks] = useState<WebhookRead[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [justCreated, setJustCreated] = useState<WebhookCreated | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    fetchWebhooks().then(setWebhooks).catch(() => setWebhooks([]));
  }, []);

  function refresh() {
    fetchWebhooks().then(setWebhooks).catch(() => {});
  }

  if (webhooks === null) {
    return (
      <div className="space-y-2">
        <div className="h-12 animate-pulse rounded bg-flaeche-1" />
        <div className="h-12 animate-pulse rounded bg-flaeche-1" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {justCreated && (
        <SecretReveal
          webhook={justCreated}
          onDismiss={() => setJustCreated(null)}
        />
      )}

      <div className="flex items-center justify-between gap-3">
        <ContractDisclosure />
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="btn btn-sekundaer inline-flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            {t("addNew")}
          </button>
        )}
      </div>

      {adding && (
        <WebhookForm
          mode="create"
          onCancel={() => setAdding(false)}
          onCreated={(w) => {
            setAdding(false);
            setJustCreated(w);
            refresh();
            toast.show({
              message: t("createdToast"),
              variant: "success",
            });
          }}
        />
      )}

      {webhooks.length === 0 && !adding && (
        <p className="text-sm text-text-sekundaer">
          {t("noneYet")}
        </p>
      )}

      {webhooks.length > 0 && (
        <div className="divide-y divide-border-subtle rounded-lg border border-trennlinie bg-seite">
          {webhooks.map((w) =>
            editingId === w.id ? (
              <div key={w.id} className="p-3">
                <WebhookForm
                  mode="edit"
                  initial={w}
                  onCancel={() => setEditingId(null)}
                  onUpdated={() => {
                    setEditingId(null);
                    refresh();
                  }}
                />
              </div>
            ) : (
              <WebhookRow
                key={w.id}
                webhook={w}
                onEdit={() => setEditingId(w.id)}
                onAfterDelete={refresh}
                onAfterToggle={refresh}
              />
            ),
          )}
        </div>
      )}
    </div>
  );
}

// ─── Row ────────────────────────────────────────────────────────────────

function WebhookRow({
  webhook,
  onEdit,
  onAfterDelete,
  onAfterToggle,
}: {
  webhook: WebhookRead;
  onEdit: () => void;
  onAfterDelete: () => void;
  onAfterToggle: () => void;
}) {
  const t = useTranslations("webhookManager");
  const tCommon = useTranslations("common");
  const toast = useToast();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<WebhookTestResult | null>(null);
  const [showDeliveries, setShowDeliveries] = useState(false);

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await testWebhook(webhook.id);
      setTestResult(r);
    } catch {
      setTestResult({ ok: false, error_message: t("testFailedMsg") });
    } finally {
      setTesting(false);
    }
  }

  async function handleToggle() {
    try {
      await updateWebhook(webhook.id, { is_active: !webhook.is_active });
      onAfterToggle();
    } catch {
      toast.show({ message: t("statusToggleFail"), variant: "error" });
    }
  }

  function handleDelete() {
    let cancelled = false;
    toast.show({
      message: t("deleteUndoMsg"),
      variant: "undo",
      duration: 5000,
      action: {
        label: tCommon("undo"),
        onClick: () => {
          cancelled = true;
        },
      },
      onTimeout: async () => {
        if (cancelled) return;
        try {
          await deleteWebhook(webhook.id);
          onAfterDelete();
        } catch {
          toast.show({
            message: t("deleteFailToast"),
            variant: "error",
          });
        }
      },
    });
  }

  const health = getHealth(webhook, t);

  return (
    <div className="px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: `var(--${health.color})` }}
              aria-hidden
            />
            <span className="font-mono text-sm text-text-primaer break-all">
              {webhook.url}
            </span>
            {!webhook.is_active && (
              <span className="rounded-full bg-flaeche-1 px-2 py-0.5 text-xs text-text-gedaempft">
                {t("inactive")}
              </span>
            )}
          </div>
          {webhook.description && (
            <p className="mt-1 text-sm text-text-sekundaer">{webhook.description}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span
              className="rounded-full px-2 py-0.5 text-xs"
              style={
                webhook.trigger_mode === "manual"
                  ? { background: "rgba(201,169,97,0.12)", color: "var(--am-gold-beschriftung)" }
                  : { background: "var(--am-flaeche-1)", color: "var(--am-text-sekundaer)" }
              }
              title={
                webhook.trigger_mode === "manual"
                  ? t("manualTooltip")
                  : t("autoTooltip")
              }
            >
              {webhook.trigger_mode === "manual"
                ? t("manualLabel")
                : t("autoLabel")}
            </span>
            {webhook.events.map((ev) => (
              <span
                key={ev}
                className="rounded-full bg-flaeche-1 px-2 py-0.5 text-xs text-text-sekundaer"
              >
                {WEBHOOK_EVENT_LABELS[ev as WebhookEvent] ?? ev}
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs text-text-gedaempft">{health.label}</p>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleTest}
            className="btn btn-still inline-flex items-center gap-1"
            disabled={testing}
            aria-label={t("testAria")}
          >
            <RefreshCw
              className={"h-3.5 w-3.5" + (testing ? " animate-spin" : "")}
              strokeWidth={1.75}
            />
            {testing ? t("testing") : t("test")}
          </button>
          <button
            type="button"
            onClick={handleToggle}
            className="rounded-md p-1.5 text-text-gedaempft transition hover:bg-flaeche-1 hover:text-text-primaer"
            aria-label={webhook.is_active ? t("deactivate") : t("activate")}
            title={webhook.is_active ? t("deactivate") : t("activate")}
          >
            {webhook.is_active ? (
              <XCircle className="h-3.5 w-3.5" strokeWidth={1.75} />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.75} />
            )}
          </button>
          <button
            type="button"
            onClick={onEdit}
            className="rounded-md p-1.5 text-text-gedaempft transition hover:bg-flaeche-1 hover:text-text-primaer"
            aria-label={t("editAria")}
          >
            <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="rounded-md p-1.5 text-text-gedaempft transition hover:bg-flaeche-1"
            aria-label={t("deleteAria")}
          >
            <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
        </div>
      </div>

      {testResult && (
        <div
          className="mt-3 rounded-md border px-3 py-2 text-xs"
          style={
            testResult.ok
              ? {
                  borderColor: "var(--am-erfolg)",
                  color: "var(--am-erfolg)",
                  background: "rgba(74,124,89,0.06)",
                }
              : {
                  borderColor: "var(--am-fehler)",
                  color: "var(--am-fehler)",
                  background: "rgba(163,58,47,0.06)",
                }
          }
        >
          <p className="font-medium">
            {testResult.ok ? t("testSuccess") : t("testFail")}
          </p>
          <p className="mt-1 opacity-90">
            {testResult.ok
              ? `HTTP ${testResult.status_code}${
                  testResult.elapsed_ms != null
                    ? ` · ${testResult.elapsed_ms} ms`
                    : ""
                }`
              : testResult.error_message ??
                `HTTP ${testResult.status_code ?? "?"}: ${testResult.response_body ?? ""}`}
          </p>
        </div>
      )}

      <button
        type="button"
        onClick={() => setShowDeliveries((v) => !v)}
        className="mt-3 inline-flex items-center gap-1 text-xs text-text-sekundaer hover:text-text-primaer"
      >
        {showDeliveries ? (
          <ChevronUp className="h-3 w-3" strokeWidth={2} />
        ) : (
          <ChevronDown className="h-3 w-3" strokeWidth={2} />
        )}
        {t("lastDeliveries")}
      </button>

      {showDeliveries && <DeliveryList webhookId={webhook.id} />}
    </div>
  );
}

function getHealth(
  w: WebhookRead,
  t: (key: string, values?: Record<string, string | number>) => string,
): { color: string; label: string } {
  if (!w.is_active) return { color: "am-text-gedaempft", label: t("healthDeactivated") };
  const ts = (v: string | null) => (v ? new Date(v).getTime() : 0);
  const lastOk = ts(w.last_success_at);
  const lastFail = ts(w.last_failure_at);
  if (!lastOk && !lastFail)
    return { color: "am-text-gedaempft", label: t("healthNoDeliveries") };
  if (lastFail > lastOk) {
    return {
      color: "am-fehler",
      label: w.last_failure_msg
        ? t("healthLastFailWithMsg", {
            when: formatRelative(w.last_failure_at),
            msg: w.last_failure_msg,
          })
        : t("healthLastFail", { when: formatRelative(w.last_failure_at) }),
    };
  }
  return {
    color: "am-erfolg",
    label: t("healthLastOk", { when: formatRelative(w.last_success_at) }),
  };
}

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ─── Delivery list ──────────────────────────────────────────────────────

function DeliveryList({ webhookId }: { webhookId: string }) {
  const t = useTranslations("webhookManager");
  const [items, setItems] = useState<WebhookDelivery[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDeliveries(webhookId, 50)
      .then((r) => {
        if (!cancelled) setItems(r);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, [webhookId]);

  if (items === null) {
    return <p className="mt-2 text-xs text-text-gedaempft">{t("loadingDeliveries")}</p>;
  }

  if (items.length === 0) {
    return <p className="mt-2 text-xs text-text-gedaempft">{t("noDeliveries")}</p>;
  }

  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-text-gedaempft">
            <th className="px-2 py-1 text-left font-normal">{t("colTime")}</th>
            <th className="px-2 py-1 text-left font-normal">{t("colEvent")}</th>
            <th className="px-2 py-1 text-left font-normal">{t("colStatus")}</th>
            <th className="px-2 py-1 text-left font-normal">{t("colResponse")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((d) => (
            <tr key={d.id} className="border-t border-trennlinie">
              <td className="px-2 py-1 align-top font-mono">
                {formatRelative(d.created_at)}
              </td>
              <td className="px-2 py-1 align-top">
                {WEBHOOK_EVENT_LABELS[d.event as WebhookEvent] ?? d.event}
              </td>
              <td
                className="px-2 py-1 align-top"
                style={{
                  color:
                    d.status_code && d.status_code >= 200 && d.status_code < 300
                      ? "var(--am-erfolg)"
                      : "var(--am-fehler)",
                }}
              >
                {d.status_code ?? "—"}
              </td>
              <td className="px-2 py-1 align-top text-text-sekundaer">
                {d.error_message
                  ? d.error_message
                  : d.response_body
                  ? d.response_body.slice(0, 80)
                  : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Form ────────────────────────────────────────────────────────────────

function WebhookForm({
  mode,
  initial,
  onCancel,
  onCreated,
  onUpdated,
}: {
  mode: "create" | "edit";
  initial?: WebhookRead;
  onCancel: () => void;
  onCreated?: (w: WebhookCreated) => void;
  onUpdated?: () => void;
}) {
  const t = useTranslations("webhookManager.form");
  const tCommon = useTranslations("common");
  const [url, setUrl] = useState(initial?.url ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [events, setEvents] = useState<WebhookEvent[]>(
    initial?.events ?? ["meeting.ready"],
  );
  const [triggerMode, setTriggerMode] = useState<"manual" | "auto">(
    initial?.trigger_mode ?? "manual",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleEvent(ev: WebhookEvent) {
    setEvents((prev) =>
      prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev],
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!url.trim()) {
      setError(t("errEmptyUrl"));
      return;
    }
    if (events.length === 0) {
      setError(t("errNoEvent"));
      return;
    }
    setSaving(true);
    try {
      if (mode === "create") {
        const created = await createWebhook({
          url: url.trim(),
          description: description.trim(),
          events,
          trigger_mode: triggerMode,
        });
        onCreated?.(created);
      } else if (initial) {
        await updateWebhook(initial.id, {
          url: url.trim(),
          description: description.trim(),
          events,
          trigger_mode: triggerMode,
        });
        onUpdated?.();
      }
    } catch (err: unknown) {
      console.error("save webhook failed", err);
      setError(t("errSave"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-md bg-flaeche-1 p-4">
      <label className="block">
        <span className="block text-xs font-medium text-text-sekundaer">
          {t("urlLabel")}
        </span>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={t("urlPlaceholder")}
          className="input mt-1 w-full"
          disabled={saving}
          autoFocus={mode === "create"}
        />
      </label>

      <label className="block">
        <span className="block text-xs font-medium text-text-sekundaer">
          {t("descLabel")}
        </span>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("descPlaceholder")}
          maxLength={500}
          className="input mt-1 w-full"
          disabled={saving}
        />
      </label>

      <fieldset>
        <legend className="block text-xs font-medium text-text-sekundaer">
          {t("eventsLegend")}
        </legend>
        <div className="mt-1 flex flex-wrap gap-3">
          {WEBHOOK_EVENTS.map((ev) => (
            <label key={ev} className="inline-flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={events.includes(ev)}
                onChange={() => toggleEvent(ev)}
                disabled={saving}
              />
              <span>{WEBHOOK_EVENT_LABELS[ev]}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="block text-xs font-medium text-text-sekundaer">
          {t("triggerLegend")}
        </legend>
        <div className="mt-2 space-y-2">
          <label className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="trigger-mode"
              value="manual"
              checked={triggerMode === "manual"}
              onChange={() => setTriggerMode("manual")}
              disabled={saving}
              className="mt-1"
            />
            <span>
              <span className="font-medium text-text-primaer">{t("manualOption")}</span>
              <span className="ml-2 text-xs text-text-gedaempft">
                {t("manualHint")}
              </span>
            </span>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="radio"
              name="trigger-mode"
              value="auto"
              checked={triggerMode === "auto"}
              onChange={() => setTriggerMode("auto")}
              disabled={saving}
              className="mt-1"
            />
            <span>
              <span className="font-medium text-text-primaer">{t("autoOption")}</span>
              <span className="ml-2 text-xs text-text-gedaempft">
                {t("autoHint")}
              </span>
            </span>
          </label>
        </div>
      </fieldset>

      {error && (
        <p className="text-sm" style={{ color: "var(--am-fehler)" }}>
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 border-t border-trennlinie pt-3">
        <button
          type="button"
          onClick={onCancel}
          className="btn btn-still"
          disabled={saving}
        >
          {tCommon("cancel")}
        </button>
        <button type="submit" className="btn btn-primaer" disabled={saving}>
          {saving ? t("saving") : mode === "edit" ? t("save") : t("create")}
        </button>
      </div>
    </form>
  );
}

// ─── One-time Secret Reveal ────────────────────────────────────────────

function SecretReveal({
  webhook,
  onDismiss,
}: {
  webhook: WebhookCreated;
  onDismiss: () => void;
}) {
  const t = useTranslations("webhookManager");
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(webhook.secret).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        borderColor: "var(--am-gold-500)",
        background: "rgba(201,169,97,0.08)",
      }}
    >
      <h4 className="text-sm font-medium text-text-primaer">
        {t("secretTitle")}
      </h4>
      <p className="mt-1 text-xs text-text-sekundaer">
        {t("secretHintBefore")}
        <code className="mx-1 rounded bg-seite px-1 font-mono">X-Insilo-Signature</code>
        {t("secretHintAfter")}
      </p>
      <div className="mt-3 flex items-center gap-2">
        <code className="flex-1 break-all rounded-md border border-trennlinie bg-seite px-2 py-1.5 font-mono text-xs">
          {webhook.secret}
        </code>
        <button
          type="button"
          onClick={copy}
          className="btn btn-sekundaer inline-flex items-center gap-1"
        >
          <Copy className="h-3.5 w-3.5" strokeWidth={1.75} />
          {copied ? t("copied") : t("copy")}
        </button>
      </div>
      <div className="mt-3 flex justify-end">
        <button type="button" onClick={onDismiss} className="btn btn-still">
          {t("dismiss")}
        </button>
      </div>
    </div>
  );
}

// ─── Contract Disclosure ───────────────────────────────────────────────

function ContractDisclosure() {
  const t = useTranslations("webhookManager");
  // Embed translated comments into the otherwise code-shaped strings.
  // We keep the surrounding code identical across locales — only the
  // human-readable comment / placeholder text varies.
  const deliveryIdHint = t("contractDeliveryIdHint");
  const upsertComment = t("contractUpsertComment");
  return (
    <details className="group text-xs text-text-sekundaer">
      <summary className="cursor-pointer select-none hover:text-text-primaer">
        {t("contractToggle")}
      </summary>
      <div className="mt-3 space-y-3 rounded-md border border-trennlinie bg-flaeche-1 p-3 leading-relaxed">
        <div>
          <p className="font-medium text-text-primaer">{t("contractHeader")}</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 font-mono text-[11px]">
            <li>X-Insilo-Event: meeting.ready</li>
            <li>X-Insilo-Delivery-ID: &lt;{deliveryIdHint}&gt;</li>
            <li>X-Insilo-Signature: sha256=&lt;HMAC-SHA256(secret, raw body)&gt;</li>
          </ul>
        </div>
        <div>
          <p className="font-medium text-text-primaer">{t("contractReceiverExample")}</p>
          <pre className="mt-1 overflow-x-auto rounded bg-seite p-2 font-mono text-[11px] text-text-primaer">{`raw = request.body
sig = request.headers["x-insilo-signature"]
expected = "sha256=" + hmac_sha256(secret, raw).hexdigest()
if not hmac.compare_digest(sig, expected):
    return 401
if already_processed(request.headers["x-insilo-delivery-id"]):
    return 200
# ${upsertComment}
return 200`}</pre>
        </div>
        <p>
          {t("contractRetryBefore")}
          <code className="mx-1 rounded bg-seite px-1 font-mono">X-Insilo-Delivery-ID</code>
          {t("contractRetryAfter")}
        </p>
        <p>
          {t("contractSpecBefore")}
          <span className="ml-1 font-mono">{t("contractSpecPath")}</span>
        </p>
      </div>
    </details>
  );
}
