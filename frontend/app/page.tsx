"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { listMeetings, type MeetingDto } from "@/lib/api/meetings";
import { formatDuration, formatMeetingDate } from "@/lib/format";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; meetings: MeetingDto[] }
  | { kind: "error"; message: string };

export default function Home() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    listMeetings()
      .then((meetings) => {
        if (!cancelled) setState({ kind: "ok", meetings });
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err instanceof ApiError
            ? `Backend nicht erreichbar (HTTP ${err.status}).`
            : "Backend nicht erreichbar. Läuft `uvicorn` auf Port 8000?";
        setState({ kind: "error", message: msg });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto max-w-[1280px] px-6 py-10 md:px-12 md:py-16">
      <div className="mb-10 flex items-baseline justify-between">
        <h1 className="text-3xl font-medium md:text-4xl">Besprechungen</h1>
        {state.kind === "ok" && state.meetings.length > 0 && (
          <p className="mono text-xs uppercase tracking-[0.08em] text-text-meta">
            {state.meetings.length}{" "}
            {state.meetings.length === 1 ? "Aufnahme" : "Aufnahmen"}
          </p>
        )}
      </div>

      {state.kind === "loading" && <ListSkeleton />}

      {state.kind === "error" && <ErrorState message={state.message} />}

      {state.kind === "ok" && state.meetings.length === 0 && <EmptyState />}

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
                    {formatMeetingDate(Date.parse(m.created_at))} ·{" "}
                    <span className="mono">{m.status}</span>
                  </p>
                </div>
                <p className="mono shrink-0 text-[0.8125rem] font-medium text-text-meta">
                  {formatDuration(m.duration_ms)}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-3" aria-live="polite" aria-busy="true">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-[72px] animate-pulse rounded-lg bg-surface-soft"
        />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-border-subtle bg-white p-12 text-center">
      <p className="font-display text-xl font-medium">Noch keine Aufnahmen</p>
      <p className="mx-auto mt-3 max-w-[420px] text-text-secondary">
        Starten Sie Ihre erste Besprechung. Audio wird auf der Olares-Box
        gespeichert — lokal auf Ihrer Hardware, niemals in der Cloud.
      </p>
      <Link href="/aufnahme" className="btn-primary mt-8 inline-flex">
        Aufnahme starten
      </Link>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-white p-12 text-center">
      <p className="font-display text-xl font-medium">Verbindung unterbrochen</p>
      <p className="mx-auto mt-3 max-w-[480px] text-text-secondary">{message}</p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="btn-secondary mt-8 inline-flex"
      >
        Erneut versuchen
      </button>
    </div>
  );
}
