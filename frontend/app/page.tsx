"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listMeetings, type Meeting } from "@/lib/db";
import { formatDuration, formatMeetingDate } from "@/lib/format";

export default function Home() {
  const [meetings, setMeetings] = useState<Meeting[] | null>(null);

  useEffect(() => {
    listMeetings().then(setMeetings);
  }, []);

  return (
    <main className="mx-auto max-w-[1280px] px-6 py-10 md:px-12 md:py-16">
      <div className="mb-10 flex items-baseline justify-between">
        <h1 className="text-3xl font-medium md:text-4xl">Besprechungen</h1>
        {meetings && meetings.length > 0 && (
          <p className="mono text-xs uppercase tracking-[0.08em] text-text-meta">
            {meetings.length}{" "}
            {meetings.length === 1 ? "Aufnahme" : "Aufnahmen"}
          </p>
        )}
      </div>

      {meetings === null && <ListSkeleton />}

      {meetings && meetings.length === 0 && <EmptyState />}

      {meetings && meetings.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border-subtle bg-white">
          {meetings.map((m) => (
            <Link key={m.id} href={`/m/${m.id}`} className="block">
              <div className="meeting-row">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-base font-medium text-text-primary">
                    {m.title}
                  </p>
                  <p className="mt-1 text-[0.8125rem] text-text-meta">
                    {formatMeetingDate(m.createdAt)} · lokal gespeichert
                  </p>
                </div>
                <p className="mono shrink-0 text-[0.8125rem] font-medium text-text-meta">
                  {formatDuration(m.durationMs)}
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
      <p className="font-display text-xl font-medium">
        Noch keine Aufnahmen
      </p>
      <p className="mx-auto mt-3 max-w-[420px] text-text-secondary">
        Starten Sie Ihre erste Besprechung. Audio wird vorerst nur lokal in
        Ihrem Browser gespeichert — keine Daten verlassen das Gerät.
      </p>
      <Link href="/aufnahme" className="btn-primary mt-8 inline-flex">
        Aufnahme starten
      </Link>
    </div>
  );
}
