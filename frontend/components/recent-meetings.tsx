"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusPill } from "@/components/status-pill";
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
            ? `Backend nicht erreichbar (HTTP ${err.status}).`
            : "Backend nicht erreichbar.";
        setState({ kind: "error", message: msg });
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [limit]);

  return (
    <section>
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <p className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
          Zuletzt aufgenommen
        </p>
        {state.kind === "ok" && state.total > limit && (
          <Link
            href="/besprechungen"
            className="mono inline-flex items-center gap-1 text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta transition hover:text-text-primary"
          >
            Alle anzeigen
            <ArrowRight className="h-3 w-3" strokeWidth={2} />
          </Link>
        )}
      </div>

      {state.kind === "loading" && (
        <div className="space-y-2" aria-live="polite" aria-busy="true">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="h-[60px] animate-pulse rounded-lg bg-surface-soft"
            />
          ))}
        </div>
      )}

      {state.kind === "error" && (
        <div className="rounded-lg border border-border-subtle bg-white p-6 text-center">
          <p className="text-sm text-text-secondary">{state.message}</p>
        </div>
      )}

      {state.kind === "ok" && state.meetings.length === 0 && (
        <div className="rounded-lg border border-border-subtle bg-white p-8 text-center">
          <p className="text-sm text-text-secondary">
            Noch keine Aufnahmen — Ihre erste startet hier oben.
          </p>
        </div>
      )}

      {state.kind === "ok" && state.meetings.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border-subtle bg-white">
          {state.meetings.map((m) => (
            <Link key={m.id} href={`/m/${m.id}`} className="block">
              <div className="meeting-row">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-base font-medium text-text-primary">
                    {m.title}
                  </p>
                  <p className="mt-1 text-[0.8125rem] text-text-meta">
                    {formatMeetingDate(Date.parse(m.created_at))}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-4">
                  <StatusPill status={m.status} />
                  <p className="mono text-[0.8125rem] font-medium text-text-meta">
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
