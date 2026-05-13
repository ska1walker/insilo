"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import { SummaryView } from "@/components/summary-view";
import { ApiError } from "@/lib/api/client";
import {
  deleteMeeting,
  getMeeting,
  retrySummary,
  type MeetingDto,
  type Transcript,
} from "@/lib/api/meetings";
import { formatBytes, formatDuration, formatMeetingDate } from "@/lib/format";

type Loaded =
  | { kind: "loading" }
  | { kind: "ok"; meeting: MeetingDto }
  | { kind: "not-found" }
  | { kind: "error"; message: string };

const POLLING_STATUS = new Set([
  "queued",
  "transcribing",
  "summarizing",
  "embedding",
  "uploading",
]);

export default function MeetingDetail() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [state, setState] = useState<Loaded>({ kind: "loading" });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      try {
        const m = await getMeeting(params.id);
        if (cancelled) return;
        setState({ kind: "ok", meeting: m });
        if (POLLING_STATUS.has(m.status) && !cancelled) {
          timerRef.current = setTimeout(tick, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setState({ kind: "not-found" });
        } else if (err instanceof ApiError) {
          setState({ kind: "error", message: `Backend antwortete mit HTTP ${err.status}.` });
        } else {
          setState({ kind: "error", message: "Backend nicht erreichbar." });
        }
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [params.id]);

  const [retrying, setRetrying] = useState(false);

  async function onRetrySummary() {
    if (state.kind !== "ok") return;
    setRetrying(true);
    try {
      await retrySummary(state.meeting.id);
      // Optimistically flip to summarizing so the poll picks it up.
      setState({
        kind: "ok",
        meeting: { ...state.meeting, status: "summarizing", error_message: null },
      });
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(async () => {
        try {
          const m = await getMeeting(state.meeting.id);
          setState({ kind: "ok", meeting: m });
        } catch {/* poll loop handles errors */}
      }, 1500);
    } catch (err) {
      console.error("retry-summary failed", err);
      window.alert("Erneutes Zusammenfassen fehlgeschlagen. Bitte später erneut versuchen.");
    } finally {
      setRetrying(false);
    }
  }

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

      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-3xl font-medium md:text-4xl">{meeting.title}</h1>
        <StatusPill status={meeting.status} />
      </div>

      <div className="mono mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-meta">
        <span>{formatMeetingDate(Date.parse(meeting.created_at))}</span>
        <span>·</span>
        <span>{formatDuration(meeting.duration_ms)}</span>
        <span>·</span>
        <span>{formatBytes(meeting.byte_size)}</span>
        <span>·</span>
        <span>{meeting.mime_type}</span>
      </div>

      {meeting.audio_url && (
        <div className="mt-10 rounded-lg border border-border-subtle bg-white p-6">
          <audio src={meeting.audio_url} controls preload="metadata" className="w-full" />
        </div>
      )}

      {meeting.status === "failed" && (
        <section className="mt-10 rounded-lg border border-border-subtle bg-white p-6">
          <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-recording">
            Verarbeitung fehlgeschlagen
          </p>
          <p className="mt-2 text-sm text-text-secondary">
            {meeting.error_message ?? "Unbekannter Fehler."}
          </p>
          {meeting.transcript && (
            <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-border-subtle pt-4">
              <p className="text-xs text-text-secondary">
                Transkript ist vorhanden. Sie können die Zusammenfassung
                erneut anstoßen — z.&nbsp;B. nachdem Sie unter{" "}
                <Link href="/einstellungen" className="underline">
                  Einstellungen
                </Link>{" "}
                einen erreichbaren LLM-Endpunkt eingetragen haben.
              </p>
              <button
                type="button"
                onClick={onRetrySummary}
                disabled={retrying}
                className="btn-secondary"
              >
                {retrying ? "Wird angestoßen…" : "Erneut zusammenfassen"}
              </button>
            </div>
          )}
        </section>
      )}

      {POLLING_STATUS.has(meeting.status) && (
        <section className="mt-10 rounded-lg border border-border-subtle bg-surface-soft p-6">
          <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
            Verarbeitung
          </p>
          <p className="mt-2 text-sm text-text-secondary">
            Die Aufnahme wird transkribiert. Diese Ansicht aktualisiert sich automatisch.
          </p>
        </section>
      )}

      {meeting.summary && (
        <section className="mt-12">
          <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
            <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
              Zusammenfassung · {meeting.summary.template_name}
            </p>
            <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
              {meeting.summary.llm_model} · {Math.round(meeting.summary.generation_time_ms / 1000)}s
            </p>
          </div>
          <div className="rounded-lg border border-border-subtle bg-white p-8">
            <SummaryView summary={meeting.summary} />
          </div>
        </section>
      )}

      {meeting.transcript && (
        <TranscriptView transcript={meeting.transcript} />
      )}

      <div className="mt-16 flex justify-end">
        <button type="button" onClick={onDelete} className="btn-tertiary text-recording">
          Aufnahme löschen
        </button>
      </div>
    </main>
  );
}

function TranscriptView({ transcript }: { transcript: Transcript }) {
  return (
    <section className="mt-12">
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
          Transkript
        </p>
        <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
          {transcript.whisper_model} · {transcript.language} · {transcript.word_count} Wörter
        </p>
      </div>

      <div className="rounded-lg border border-border-subtle bg-white p-8">
        {transcript.segments.length === 0 && (
          <p className="text-sm text-text-meta">
            Keine Sprache erkannt. Die Aufnahme enthielt nur Stille oder Hintergrundrauschen.
          </p>
        )}

        {transcript.segments.map((seg, i) => (
          <div
            key={i}
            className="grid grid-cols-[80px_1fr] gap-4 py-3 md:grid-cols-[100px_1fr] md:gap-6"
          >
            <div>
              <p className="mono text-[0.8125rem] font-medium text-text-meta">
                [{formatTime(seg.start)}]
              </p>
              {seg.speaker && (
                <p
                  className="mono mt-1 text-[0.8125rem] font-medium uppercase tracking-[0.02em]"
                  style={{ color: "var(--gold)" }}
                >
                  {seg.speaker}
                </p>
              )}
            </div>
            <p className="text-base leading-relaxed text-text-primary">{seg.text}</p>
          </div>
        ))}
      </div>

    </section>
  );
}

function formatTime(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}
