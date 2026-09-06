"use client";

import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import { TagPillRow } from "@/components/tag-pill";
import { ApiError } from "@/lib/api/client";
import { listMeetings, type MeetingDto } from "@/lib/api/meetings";
import { formatDuration, formatMeetingDate } from "@/lib/format";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; meetings: MeetingDto[]; total: number }
  | { kind: "error"; message: string };

const PIPELINE_STATUSES = new Set([
  "queued",
  "transcribing",
  "summarizing",
  "embedding",
  "uploading",
]);

export function RecentMeetings({ limit = 5 }: { limit?: number }) {
  const t = useTranslations("meeting");
  const tErrors = useTranslations("errors");
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const all = await listMeetings();
        if (cancelled) return;
        setState({ kind: "ok", meetings: all.slice(0, limit), total: all.length });

        // Keep polling while anything in the visible slice is still in-pipeline.
        const stillWorking = all
          .slice(0, limit)
          .some((m) => PIPELINE_STATUSES.has(m.status));
        if (stillWorking && !cancelled) {
          timer = setTimeout(tick, 3000);
        }
      } catch (err) {
        if (cancelled) return;
        const msg =
          err instanceof ApiError
            ? t("backendUnreachableHttp", { status: err.status })
            : tErrors("network");
        setState({ kind: "error", message: msg });
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [limit, t, tErrors]);

  return (
    <section>
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <p className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-gedaempft">
          {t("recentTitle")}
        </p>
        {state.kind === "ok" && state.total > limit && (
          <Link
            href="/besprechungen"
            className="mono inline-flex items-center gap-1 text-[0.6875rem] uppercase tracking-[0.08em] text-text-gedaempft transition hover:text-text-primaer"
          >
            {t("viewAll")}
            <ArrowRight className="h-3 w-3" strokeWidth={2} />
          </Link>
        )}
      </div>

      {state.kind === "loading" && (
        <div className="space-y-2" aria-live="polite" aria-busy="true">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="h-[60px] rounded-lg bg-flaeche-3"
            />
          ))}
        </div>
      )}

      {state.kind === "error" && (
        <div className="rounded-lg border border-trennlinie bg-seite p-6 text-center">
          <p className="text-sm text-text-sekundaer">{state.message}</p>
        </div>
      )}

      {state.kind === "ok" && state.meetings.length === 0 && (
        <div className="rounded-lg border border-trennlinie bg-seite p-8 text-center">
          <p className="text-sm text-text-sekundaer">
            {t("listEmptyHome")}
          </p>
        </div>
      )}

      {state.kind === "ok" && state.meetings.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-trennlinie bg-seite">
          {state.meetings.map((m, i) => (
            <Link
              key={m.id}
              href={`/m/${m.id}`}
              className="stagger-in block"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              <div className="meeting-row">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-base font-medium text-text-primaer">
                    {m.title}
                  </p>
                  <p className="mt-1 text-[0.8125rem] text-text-gedaempft">
                    {formatMeetingDate(Date.parse(m.created_at))}
                  </p>
                  {m.tags && m.tags.length > 0 && (
                    <div className="mt-2">
                      <TagPillRow tags={m.tags} max={3} />
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-4">
                  <StatusPill status={m.status} />
                  <p className="mono text-[0.8125rem] font-medium text-text-gedaempft">
                    {formatDuration(m.duration_ms)}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
