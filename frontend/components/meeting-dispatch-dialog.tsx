"use client";

import { Loader2, Send, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import { ApiError } from "@/lib/api/client";
import { dispatchMeeting } from "@/lib/api/meetings";
import { fetchWebhooks, type WebhookRead } from "@/lib/api/webhooks";

/**
 * Modal: lässt den User pro Meeting auswählen, an welche externen
 * Systeme (Webhooks) die `meeting.ready`-Auslieferung gehen soll.
 *
 * Wird nur für Meetings mit Status "ready" geöffnet. Bypassed
 * `trigger_mode='manual'` — die User-Aktion ist die explizite
 * Einwilligung.
 */
export function MeetingDispatchDialog({
  meetingId,
  meetingTitle,
  onClose,
}: {
  meetingId: string;
  meetingTitle: string;
  onClose: () => void;
}) {
  const toast = useToast();
  const [webhooks, setWebhooks] = useState<WebhookRead[] | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchWebhooks()
      .then((all) => {
        const ready = all.filter(
          (w) => w.is_active && w.events.includes("meeting.ready"),
        );
        setWebhooks(ready);
        // Default: alle vorausgewählt — User klickt aus wenn er nicht will
        setSelectedIds(new Set(ready.map((w) => w.id)));
      })
      .catch(() => setWebhooks([]));
  }, []);

  function toggle(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSend() {
    if (selectedIds.size === 0) return;
    setSending(true);
    try {
      const result = await dispatchMeeting(meetingId, Array.from(selectedIds));
      toast.show({
        message: `An ${result.fanout} ${
          result.fanout === 1 ? "Empfänger" : "Empfänger"
        } gesendet.`,
        variant: "success",
      });
      onClose();
    } catch (err) {
      console.error("dispatch failed", err);
      if (err instanceof ApiError) {
        toast.show({
          message: `Versand fehlgeschlagen: HTTP ${err.status}`,
          variant: "error",
        });
      } else {
        toast.show({ message: "Versand fehlgeschlagen.", variant: "error" });
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal
      aria-label="An externe Systeme senden"
    >
      <div className="relative max-h-[90vh] w-full max-w-[560px] overflow-y-auto rounded-lg border border-border-subtle bg-white p-6 shadow-2xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
          aria-label="Schließen"
        >
          <X className="h-4 w-4" strokeWidth={1.75} />
        </button>

        <h2 className="font-display text-2xl font-medium tracking-tight">
          An externe Systeme senden
        </h2>
        <p className="mt-2 text-sm text-text-secondary">
          Insilo schickt die Zusammenfassung dieser Besprechung („{meetingTitle}
          ") an die ausgewählten Empfänger. Diese Aktion bleibt auf Ihre
          ausdrückliche Bestätigung beschränkt — automatische Auslieferung
          ist pro Webhook gesondert konfigurierbar.
        </p>

        {webhooks === null ? (
          <div className="mt-5 flex items-center gap-3 rounded-md bg-surface-soft p-4 text-sm text-text-secondary">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
            Empfänger werden geladen …
          </div>
        ) : webhooks.length === 0 ? (
          <div className="mt-5 rounded-md border border-border-subtle bg-surface-soft p-4 text-sm text-text-secondary">
            Sie haben noch keine aktiven Webhooks für{" "}
            <code className="rounded bg-white px-1 font-mono">meeting.ready</code>{" "}
            angelegt. Legen Sie unter
            <span className="mx-1 font-medium">Einstellungen → Webhooks</span>
            mindestens einen Empfänger an.
          </div>
        ) : (
          <ul className="mt-5 divide-y divide-border-subtle rounded-lg border border-border-subtle bg-white">
            {webhooks.map((w) => (
              <li key={w.id} className="px-4 py-3">
                <label className="flex cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(w.id)}
                    onChange={() => toggle(w.id)}
                    disabled={sending}
                    className="mt-1"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block font-mono text-xs text-text-primary break-all">
                      {w.url}
                    </span>
                    {w.description && (
                      <span className="mt-1 block text-xs text-text-secondary">
                        {w.description}
                      </span>
                    )}
                    <span className="mt-1 inline-block rounded-full px-2 py-0.5 text-[0.6875rem]"
                      style={
                        w.trigger_mode === "manual"
                          ? { background: "rgba(201,169,97,0.12)", color: "var(--gold-deep)" }
                          : { background: "var(--surface-soft)", color: "var(--text-secondary)" }
                      }
                    >
                      {w.trigger_mode === "manual" ? "manuell" : "automatisch"}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-text-meta">
            {webhooks && webhooks.length > 0
              ? `${selectedIds.size} von ${webhooks.length} ausgewählt`
              : ""}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="btn-tertiary"
              disabled={sending}
            >
              Abbrechen
            </button>
            <button
              type="button"
              onClick={handleSend}
              disabled={sending || selectedIds.size === 0}
              className="btn-primary inline-flex items-center gap-2"
            >
              {sending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
                  Wird gesendet …
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" strokeWidth={1.75} />
                  Jetzt senden
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
