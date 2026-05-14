"use client";

import { ShieldCheck } from "lucide-react";
import { RecentMeetings } from "@/components/recent-meetings";
import { RecordingBlock } from "@/components/recording-block";

export default function Home() {
  return (
    <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12 md:py-16">
      {/* Hero · Aufnahme-Block */}
      <section className="mb-16">
        <RecordingBlock variant="compact" />
      </section>

      {/* Trennlinie zwischen Aktion und Übersicht */}
      <hr className="my-12 border-0 border-t border-border-subtle" />

      {/* Zuletzt aufgenommen */}
      <RecentMeetings limit={5} />

      {/* Trust-Badge am Fuß */}
      <div className="mt-16 flex flex-col items-center gap-3">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-full"
          style={{
            background: "var(--gold-faint)",
            border: "1px solid rgba(201, 169, 97, 0.4)",
          }}
        >
          <ShieldCheck
            className="h-5 w-5"
            style={{ color: "var(--gold-deep)" }}
            strokeWidth={1.75}
          />
        </div>
        <div className="max-w-[360px] text-center">
          <p className="text-sm font-medium text-text-primary">Datensouverän</p>
          <p className="mt-1 text-sm text-text-meta">
            Audio, Transkript und Suchindex bleiben auf Ihrer Olares-Box.
            Kein Cloud-Upload, keine Drittanbieter.
          </p>
        </div>
      </div>
    </main>
  );
}
