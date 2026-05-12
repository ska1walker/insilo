"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { deleteMeeting, getMeeting, type MeetingDto } from "@/lib/api/meetings";
import { formatBytes, formatDuration, formatMeetingDate } from "@/lib/format";

type Loaded =
  | { kind: "loading" }
  | { kind: "ok"; meeting: MeetingDto }
  | { kind: "not-found" }
  | { kind: "error"; message: string };

export default function MeetingDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [state, setState] = useState<Loaded>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    getMeeting(params.id)
      .then((meeting) => {
        if (!cancelled) setState({ kind: "ok", meeting });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setState({ kind: "not-found" });
        } else if (err instanceof ApiError) {
          setState({ kind: "error", message: `Backend antwortete mit HTTP ${err.status}.` });
        } else {
          setState({ kind: "error", message: "Backend nicht erreichbar." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  async function onDelete() {
    if (state.kind !== "ok") return;
    const ok = window.confirm(
      `„${state.meeting.title}" endgültig löschen? Dieser Schritt kann nicht rückgängig gemacht werden.`,
    );
    if (!ok) return;
    try {
      await deleteMeeting(state.meeting.id);
      router.push("/");
    } catch (err) {
      console.error("delete failed", err);
      window.alert("Löschen fehlgeschlagen. Bitte erneut versuchen.");
    }
  }

  if (state.kind === "loading") {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-16 md:px-12">
        <div className="h-8 w-1/2 animate-pulse rounded bg-surface-soft" />
        <div className="mt-4 h-4 w-1/3 animate-pulse rounded bg-surface-soft" />
        <div className="mt-12 h-14 w-full animate-pulse rounded bg-surface-soft" />
      </main>
    );
  }

  if (state.kind === "not-found") {
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

  if (state.kind === "error") {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-24 text-center md:px-12">
        <p className="font-display text-xl font-medium">Verbindung unterbrochen</p>
        <p className="mx-auto mt-3 max-w-[420px] text-text-secondary">{state.message}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="btn-secondary mt-8 inline-flex"
        >
          Erneut versuchen
        </button>
      </main>
    );
  }

  const { meeting } = state;

  return (
    <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12 md:py-16">
      <Link href="/" className="btn-tertiary -ml-3 mb-8 inline-flex">
        ← Übersicht
      </Link>

      <h1 className="text-3xl font-medium md:text-4xl">{meeting.title}</h1>

      <div className="mono mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-meta">
        <span>{formatMeetingDate(Date.parse(meeting.created_at))}</span>
        <span>·</span>
        <span>{formatDuration(meeting.duration_ms)}</span>
        <span>·</span>
        <span>{formatBytes(meeting.byte_size)}</span>
        <span>·</span>
        <span>{meeting.mime_type}</span>
        <span>·</span>
        <span>status: {meeting.status}</span>
      </div>

      {meeting.audio_url && (
        <div className="mt-10 rounded-lg border border-border-subtle bg-white p-6">
          <audio src={meeting.audio_url} controls preload="metadata" className="w-full" />
        </div>
      )}

      <section className="mt-12 rounded-lg border border-border-subtle bg-surface-soft p-6">
        <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
          Phase 2 — folgt
        </p>
        <p className="mt-2 text-sm text-text-secondary">
          In der nächsten Phase erscheint hier das automatisch erzeugte
          Transkript (Whisper) mit Sprecher-Trennung sowie eine
          KI-Zusammenfassung über das gewählte Template.
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
