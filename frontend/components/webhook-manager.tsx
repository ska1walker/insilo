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
        <div className="h-12 animate-pulse rounded bg-surface-soft" />
        <div className="h-12 animate-pulse rounded bg-surface-soft" />
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

      <div className="flex justify-end">
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="btn-secondary inline-flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            Neuen Webhook hinzufügen
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
              message: "Webhook angelegt.",
              variant: "success",
            });
          }}
        />
      )}

      {webhooks.length === 0 && !adding && (
        <p className="text-sm text-text-secondary">
          Noch keine Webhooks. Legen Sie über „Neuen Webhook hinzufügen" eine
          Ziel-URL an — Insilo schickt dann bei jeder Statusänderung einer
          Besprechung einen signierten POST-Request dorthin.
        </p>
      )}

      {webhooks.length > 0 && (
        <div className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-white">
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
      setTestResult({ ok: false, error_message: "Test fehlgeschlagen." });
    } finally {
      setTesting(false);
    }
  }

  async function handleToggle() {
    try {
      await updateWebhook(webhook.id, { is_active: !webhook.is_active });
      onAfterToggle();
    } catch {
      toast.show({ message: "Konnte Status nicht ändern.", variant: "error" });
    }
  }

  function handleDelete() {
    let cancelled = false;
    toast.show({
      message: "Webhook wird gelöscht",
      variant: "undo",
      duration: 5000,
      action: {
        label: "Rückgängig",
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
            message: "Webhook konnte nicht gelöscht werden.",
            variant: "error",
          });
        }
      },
    });
  }

  const health = getHealth(webhook);

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
            <span className="font-mono text-sm text-text-primary break-all">
              {webhook.url}
            </span>
            {!webhook.is_active && (
              <span className="rounded-full bg-surface-soft px-2 py-0.5 text-xs text-text-meta">
                inaktiv
              </span>
            )}
          </div>
          {webhook.description && (
            <p className="mt-1 text-sm text-text-secondary">{webhook.description}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {webhook.events.map((ev) => (
              <span
                key={ev}
                className="rounded-full bg-surface-soft px-2 py-0.5 text-xs text-text-secondary"
              >
                {WEBHOOK_EVENT_LABELS[ev as WebhookEvent] ?? ev}
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs text-text-meta">{health.label}</p>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleTest}
            className="btn-tertiary inline-flex items-center gap-1"
            disabled={testing}
            aria-label="Webhook testen"
          >
            <RefreshCw
              className={"h-3.5 w-3.5" + (testing ? " animate-spin" : "")}
              strokeWidth={1.75}
            />
            {testing ? "Teste …" : "Testen"}
          </button>
          <button
            type="button"
            onClick={handleToggle}
            className="rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
            aria-label={webhook.is_active ? "Deaktivieren" : "Aktivieren"}
            title={webhook.is_active ? "Deaktivieren" : "Aktivieren"}
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
            className="rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
            aria-label="Bearbeiten"
          >
            <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft"
            aria-label="Löschen"
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
                  borderColor: "var(--success)",
                  color: "var(--success)",
                  background: "rgba(74,124,89,0.06)",
                }
              : {
                  borderColor: "var(--error)",
                  color: "var(--error)",
                  background: "rgba(163,58,47,0.06)",
                }
          }
        >
          <p className="font-medium">
            {testResult.ok ? "Test erfolgreich" : "Test fehlgeschlagen"}
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
        className="mt-3 inline-flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary"
      >
        {showDeliveries ? (
          <ChevronUp className="h-3 w-3" strokeWidth={2} />
        ) : (
          <ChevronDown className="h-3 w-3" strokeWidth={2} />
        )}
        Letzte Auslieferungen
      </button>

      {showDeliveries && <DeliveryList webhookId={webhook.id} />}
    </div>
  );
}

function getHealth(w: WebhookRead): { color: string; label: string } {
  if (!w.is_active) return { color: "text-meta", label: "Deaktiviert" };
  const ts = (v: string | null) => (v ? new Date(v).getTime() : 0);
  const lastOk = ts(w.last_success_at);
  const lastFail = ts(w.last_failure_at);
  if (!lastOk && !lastFail)
    return { color: "text-meta", label: "Noch keine Auslieferung." };
  if (lastFail > lastOk) {
    return {
      color: "error",
      label: `Letzter Fehler: ${formatRelative(w.last_failure_at)}${
        w.last_failure_msg ? ` – ${w.last_failure_msg}` : ""
      }`,
    };
  }
  return {
    color: "success",
    label: `Letzte erfolgreiche Auslieferung: ${formatRelative(w.last_success_at)}`,
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
    return <p className="mt-2 text-xs text-text-meta">Wird geladen …</p>;
  }

  if (items.length === 0) {
    return <p className="mt-2 text-xs text-text-meta">Noch keine Auslieferungen.</p>;
  }

  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-text-meta">
            <th className="px-2 py-1 text-left font-normal">Zeit</th>
            <th className="px-2 py-1 text-left font-normal">Event</th>
            <th className="px-2 py-1 text-left font-normal">Status</th>
            <th className="px-2 py-1 text-left font-normal">Antwort</th>
          </tr>
        </thead>
        <tbody>
          {items.map((d) => (
            <tr key={d.id} className="border-t border-border-subtle">
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
                      ? "var(--success)"
                      : "var(--error)",
                }}
              >
                {d.status_code ?? "—"}
              </td>
              <td className="px-2 py-1 align-top text-text-secondary">
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
  const [url, setUrl] = useState(initial?.url ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [events, setEvents] = useState<WebhookEvent[]>(
    initial?.events ?? ["meeting.ready"],
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
      setError("URL darf nicht leer sein.");
      return;
    }
    if (events.length === 0) {
      setError("Mindestens ein Ereignis muss aktiv sein.");
      return;
    }
    setSaving(true);
    try {
      if (mode === "create") {
        const created = await createWebhook({
          url: url.trim(),
          description: description.trim(),
          events,
        });
        onCreated?.(created);
      } else if (initial) {
        await updateWebhook(initial.id, {
          url: url.trim(),
          description: description.trim(),
          events,
        });
        onUpdated?.();
      }
    } catch (err: unknown) {
      console.error("save webhook failed", err);
      setError("Speichern fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-md bg-surface-soft p-4">
      <label className="block">
        <span className="block text-xs font-medium text-text-secondary">
          Ziel-URL
        </span>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://duo.example.com/api/inbox"
          className="input mt-1 w-full"
          disabled={saving}
          autoFocus={mode === "create"}
        />
      </label>

      <label className="block">
        <span className="block text-xs font-medium text-text-secondary">
          Beschreibung (optional)
        </span>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="z. B. Duo Knowledge-Hub"
          maxLength={500}
          className="input mt-1 w-full"
          disabled={saving}
        />
      </label>

      <fieldset>
        <legend className="block text-xs font-medium text-text-secondary">
          Ereignisse
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

      {error && (
        <p className="text-sm" style={{ color: "var(--error)" }}>
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 border-t border-border-subtle pt-3">
        <button
          type="button"
          onClick={onCancel}
          className="btn-tertiary"
          disabled={saving}
        >
          Abbrechen
        </button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Speichert …" : mode === "edit" ? "Speichern" : "Anlegen"}
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
        borderColor: "var(--gold)",
        background: "rgba(201,169,97,0.08)",
      }}
    >
      <h4 className="text-sm font-medium text-text-primary">
        Webhook-Secret
      </h4>
      <p className="mt-1 text-xs text-text-secondary">
        Insilo signiert jeden Webhook-POST mit diesem Secret im Header
        <code className="mx-1 rounded bg-white px-1 font-mono">X-Insilo-Signature</code>.
        Speichern Sie es jetzt — es wird Ihnen nicht erneut angezeigt.
      </p>
      <div className="mt-3 flex items-center gap-2">
        <code className="flex-1 break-all rounded-md border border-border-subtle bg-white px-2 py-1.5 font-mono text-xs">
          {webhook.secret}
        </code>
        <button
          type="button"
          onClick={copy}
          className="btn-secondary inline-flex items-center gap-1"
        >
          <Copy className="h-3.5 w-3.5" strokeWidth={1.75} />
          {copied ? "Kopiert" : "Kopieren"}
        </button>
      </div>
      <div className="mt-3 flex justify-end">
        <button type="button" onClick={onDismiss} className="btn-tertiary">
          Verstanden, ausblenden
        </button>
      </div>
    </div>
  );
}
