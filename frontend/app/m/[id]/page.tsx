"use client";

import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { deleteMeeting, getMeeting, getMeetingAudio, type Meeting } from "@/lib/db";
import { formatBytes, formatDuration, formatMeetingDate } from "@/lib/format";

type Loaded = { meeting: Meeting; audioUrl: string } | "loading" | "not-found";

export default function MeetingDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [state, setState] = useState<Loaded>("loading");
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const m = await getMeeting(params.id);
      if (!m) {
        if (!cancelled) setState("not-found");
        return;
      }
      const blob = await getMeetingAudio(params.id);
      if (!blob) {
        if (!cancelled) setState("not-found");
        return;
      }
      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      if (!cancelled) setState({ meeting: m, audioUrl: url });
    })();
    return () => {
      cancelled = true;
      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
      }
    };
  }, [params.id]);

  async function onDelete() {
    const m = state !== "loading" && state !== "not-found" ? state.meeting : null;
    if (!m) return;
    const ok = window.confirm(
      `„${m.title}" endgültig löschen? Dieser Schritt kann nicht rückgängig gemacht werden.`,
    );
    if (!ok) return;
    await deleteMeeting(m.id);
    router.push("/");
  }

  if (state === "loading") {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-16 md:px-12">
        <div className="h-8 w-1/2 animate-pulse rounded bg-surface-soft" />
        <div className="mt-4 h-4 w-1/3 animate-pulse rounded bg-surface-soft" />
        <div className="mt-12 h-14 w-full animate-pulse rounded bg-surface-soft" />
      </main>
    );
  }

  if (state === "not-found") {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-24 text-center md:px-12">
        <p className="font-display text-xl font-medium">Aufnahme nicht gefunden</p>
        <p className="mx-auto mt-3 max-w-[420px] text-text-secondary">
          Diese Aufnahme existiert nicht oder wurde bereits gelöscht.
        </p>
        <Link href="/" className="btn-primary mt-8 inline-flex">
          Zur Übersicht
        </Link>
      </main>
    );
  }

  const { meeting, audioUrl } = state;

  return (
    <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12 md:py-16">
      <Link href="/" className="btn-tertiary -ml-3 mb-8 inline-flex">
        ← Übersicht
      </Link>

      <h1 className="text-3xl font-medium md:text-4xl">{meeting.title}</h1>

      <div className="mono mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-meta">
        <span>{formatMeetingDate(meeting.createdAt)}</span>
        <span>·</span>
        <span>{formatDuration(meeting.durationMs)}</span>
        <span>·</span>
        <span>{formatBytes(meeting.byteSize)}</span>
        <span>·</span>
        <span>{meeting.mimeType}</span>
      </div>

      <div className="mt-10 rounded-lg border border-border-subtle bg-white p-6">
        <audio
          src={audioUrl}
          controls
          preload="metadata"
          className="w-full"
        />
      </div>

      <section className="mt-12 rounded-lg border border-border-subtle bg-surface-soft p-6">
        <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
          Phase 2 — folgt
        </p>
        <p className="mt-2 text-sm text-text-secondary">
          In der nächsten Phase erscheint hier das automatisch erzeugte
          Transkript (Whisper) mit Sprecher-Trennung und eine
          KI-Zusammenfassung. Bis dahin ist die Aufnahme nur lokal in Ihrem
          Browser gespeichert.
        </p>
      </section>

      <div className="mt-12 flex justify-end">
        <button type="button" onClick={onDelete} className="btn-tertiary text-recording">
          Aufnahme löschen
        </button>
      </div>
    </main>
  );
}
