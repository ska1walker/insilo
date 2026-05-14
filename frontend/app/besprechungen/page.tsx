"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import { TagFilterBar } from "@/components/tag-filter-bar";
import { TagPillRow } from "@/components/tag-pill";
import { ApiError } from "@/lib/api/client";
import { listMeetings, type MeetingDto } from "@/lib/api/meetings";
import { formatDuration, formatMeetingDate } from "@/lib/format";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; meetings: MeetingDto[] }
  | { kind: "error"; message: string };

export default function Home() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const meetings = await listMeetings({ tagIds: selectedTagIds });
        if (cancelled) return;
        setState({ kind: "ok", meetings });
        const stillWorking = meetings.some((m) =>
          ["queued", "transcribing", "summarizing", "embedding", "uploading"].includes(m.status),
        );
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
  }, [selectedTagIds]);

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

      <TagFilterBar
        selectedIds={selectedTagIds}
        onChange={setSelectedTagIds}
      />

      {state.kind === "loading" && <ListSkeleton />}

      {state.kind === "error" && <ErrorState message={state.message} />}

      {state.kind === "ok" && state.meetings.length === 0 &&
        (selectedTagIds.length > 0 ? <FilteredEmpty /> : <EmptyState />)}

      {state.kind === "ok" && state.meetings.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border-subtle bg-white">
          {state.meetings.map((m, i) => (
            <Link
              key={m.id}
              href={`/m/${m.id}`}
              className="stagger-in block"
              style={{ animationDelay: `${Math.min(i, 8) * 35}ms` }}
            >
              <div className="meeting-row">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-base font-medium text-text-primary">
                    {m.title}
                  </p>
                  <p className="mt-1 text-[0.8125rem] text-text-meta">
                    {formatMeetingDate(Date.parse(m.created_at))}
                  </p>
                  {m.tags && m.tags.length > 0 && (
                    <div className="mt-2">
                      <TagPillRow tags={m.tags} max={4} />
                    </div>
                  )}
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
    </main>
  );
}

function FilteredEmpty() {
  return (
    <div className="rounded-lg border border-border-subtle bg-white p-12 text-center">
      <p className="font-display text-xl font-medium">Keine Treffer</p>
      <p className="mx-auto mt-3 max-w-[420px] text-text-secondary">
        Keine Besprechung enthält alle ausgewählten Tags. Lösen Sie einen
        Filter oder versuchen Sie es mit weniger Tags.
      </p>
    </div>
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
