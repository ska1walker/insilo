"use client";

import { Loader2, Send, X } from "@/lib/symbole";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("dispatch");
  const tCommon = useTranslations("common");
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
        message: t("sentToast", { count: result.fanout }),
        variant: "success",
      });
      onClose();
    } catch (err) {
      console.error("dispatch failed", err);
      if (err instanceof ApiError) {
        toast.show({
          message: t("sendFailedHttp", { status: err.status }),
          variant: "error",
        });
      } else {
        toast.show({ message: t("sendFailed"), variant: "error" });
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="dialog-schicht"
      role="dialog"
      aria-modal
      aria-label={t("header")}
    >
      {/* Header fix + Body scrollt + Footer sticky — selbe Struktur wie
          voice-enrollment-dialog, damit die Action-Buttons bei kleinen
          Viewports immer sichtbar bleiben. */}
      <div className="karte dialog-karte relative bg-seite" data-breite="normal">
        <div className="flex-shrink-0 border-b border-trennlinie p-6 pr-12">
          <button
            type="button"
            onClick={onClose}
            className="absolute right-4 top-4 rounded-md p-1.5 text-text-gedaempft transition hover:bg-flaeche-1 hover:text-text-primaer"
            aria-label={tCommon("close")}
          >
            <X size={16} />
          </button>
          <h2 className="font-display text-2xl font-medium tracking-tight">
            {t("header")}
          </h2>
          <p className="mt-2 text-sm text-text-sekundaer">
            {t("intro", { title: meetingTitle })}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {webhooks === null ? (
            <div className="flex items-center gap-3 rounded-md bg-flaeche-1 p-4 text-sm text-text-sekundaer">
              <Loader2 size={16} className="animate-spin" />
              {t("loadingRecipients")}
            </div>
          ) : webhooks.length === 0 ? (
            <div className="rounded-md border border-trennlinie bg-flaeche-1 p-4 text-sm text-text-sekundaer">
              {t.rich("noWebhooks", {
                code: (chunks) => (
                  <code className="rounded bg-seite px-1 font-mono">
                    {chunks}
                  </code>
                ),
                bold: (chunks) => (
                  <span className="font-medium">{chunks}</span>
                ),
              })}
            </div>
          ) : (
            <ul className="divide-y divide-trennlinie rounded-lg border border-trennlinie bg-seite">
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
                      <span className="block font-mono text-xs text-text-primaer break-all">
                        {w.url}
                      </span>
                      {w.description && (
                        <span className="mt-1 block text-xs text-text-sekundaer">
                          {w.description}
                        </span>
                      )}
                      <span
                        className="mt-1 inline-block rounded-full px-2 py-0.5 text-[0.6875rem]"
                        style={
                          w.trigger_mode === "manual"
                            ? { background: "var(--am-auswahl-flaeche)", color: "var(--am-text-primaer)" }
                            : { background: "var(--am-flaeche-1)", color: "var(--am-text-sekundaer)" }
                        }
                      >
                        {w.trigger_mode === "manual"
                          ? t("triggerManual")
                          : t("triggerAuto")}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-shrink-0 flex-wrap items-center justify-between gap-3 border-t border-trennlinie bg-seite p-6">
          <p className="text-xs text-text-gedaempft">
            {webhooks && webhooks.length > 0
              ? t("selectedCount", {
                  selected: selectedIds.size,
                  total: webhooks.length,
                })
              : ""}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-still"
              disabled={sending}
            >
              {tCommon("cancel")}
            </button>
            <button
              type="button"
              onClick={handleSend}
              disabled={sending || selectedIds.size === 0}
              className="btn btn-primaer inline-flex items-center gap-2"
            >
              {sending ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  {t("sending")}
                </>
              ) : (
                <>
                  <Send size={16} />
                  {t("send")}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
