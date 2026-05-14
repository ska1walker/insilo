"use client";

import { ArrowRight, MessageSquareQuote, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ApiError } from "@/lib/api/client";
import { ask, type AskResponse, type AskSource } from "@/lib/api/ask";
import { formatMeetingDate } from "@/lib/format";

type Phase = "idle" | "asking" | "done" | "error";

const EXAMPLES = [
  "Welche Beschlüsse wurden in den letzten Mandantengesprächen gefasst?",
  "Wer ist verantwortlich für die Cyberversicherung?",
  "Welche Wiedervorlagen sind in den nächsten zwei Wochen fällig?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(q: string) {
    const trimmed = q.trim();
    if (trimmed.length < 4) return;
    setPhase("asking");
    setError(null);
    setResult(null);
    try {
      const r = await ask(trimmed);
      setResult(r);
      setPhase("done");
    } catch (err) {
      console.error("ask failed", err);
      if (err instanceof ApiError) {
        if (err.status === 503) {
          setError(
            "Die KI-Dienste sind gerade nicht erreichbar. Bitte gleich erneut versuchen.",
          );
        } else {
          setError(`Anfrage fehlgeschlagen (HTTP ${err.status}).`);
        }
      } else {
        setError("Verbindung zum Backend unterbrochen.");
      }
      setPhase("error");
    }
  }

  return (
    <main className="mx-auto max-w-[860px] px-6 py-12 md:px-12 md:py-16">
      {/* ── Hero ──────────────────────────────────────────────────── */}
      <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
        Archiv-Suche · Grounded Q&amp;A
      </p>
      <h1 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
        Fragen Sie Ihr Meeting-Archiv.
      </h1>
      <p className="mt-4 max-w-[640px] text-text-secondary">
        Stellen Sie eine Frage in natürlicher Sprache. Insilo durchsucht die
        Transkripte und Zusammenfassungen aller Besprechungen Ihrer
        Organisation und antwortet mit Quellenangaben.
      </p>

      {/* ── Form ──────────────────────────────────────────────────── */}
      <form
        className="mt-10"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <div className="rounded-lg border border-border-subtle bg-white p-2 transition focus-within:border-text-primary">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                submit(question);
              }
            }}
            placeholder="Worüber möchten Sie etwas wissen?"
            rows={3}
            className="block w-full resize-none bg-transparent px-3 py-2 text-base leading-relaxed text-text-primary outline-none placeholder:text-text-disabled"
            disabled={phase === "asking"}
          />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border-subtle px-2 pt-2">
            <p className="text-xs text-text-meta">
              <span className="mono">⌘ ↵</span> zum Absenden · Antwort
              dauert je nach Modell 5–20 Sekunden
            </p>
            <button
              type="submit"
              className="btn-primary inline-flex items-center gap-1.5"
              disabled={phase === "asking" || question.trim().length < 4}
            >
              {phase === "asking" ? (
                <>
                  <Sparkles className="h-3.5 w-3.5 animate-pulse" strokeWidth={1.75} />
                  Sucht …
                </>
              ) : (
                <>
                  Frage stellen
                  <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                </>
              )}
            </button>
          </div>
        </div>
      </form>

      {/* ── Examples (only in idle state) ─────────────────────────── */}
      {phase === "idle" && !result && (
        <section className="mt-12">
          <div className="mb-4 flex items-baseline gap-2">
            <MessageSquareQuote
              className="h-3.5 w-3.5 text-text-meta"
              strokeWidth={1.75}
            />
            <p className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
              Beispiel-Fragen
            </p>
          </div>
          <div className="grid gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  setQuestion(ex);
                  submit(ex);
                }}
                className="group flex items-center justify-between gap-4 rounded-lg border border-border-subtle bg-white px-5 py-4 text-left transition hover:border-text-primary hover:bg-surface-soft"
              >
                <span className="text-sm leading-relaxed text-text-primary">
                  {ex}
                </span>
                <ArrowRight
                  className="h-4 w-4 shrink-0 text-text-meta transition group-hover:translate-x-0.5 group-hover:text-text-primary"
                  strokeWidth={1.75}
                />
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── Error ─────────────────────────────────────────────────── */}
      {error && (
        <div
          className="mt-10 rounded-lg border bg-white p-6"
          style={{
            borderColor: "var(--error)",
            background: "rgba(163, 58, 47, 0.04)",
          }}
        >
          <p
            className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em]"
            style={{ color: "var(--error)" }}
          >
            Fehler
          </p>
          <p className="mt-2 text-sm text-text-secondary">{error}</p>
        </div>
      )}

      {/* ── Loading skeleton ─────────────────────────────────────── */}
      {phase === "asking" && (
        <div className="mt-10 space-y-3" aria-busy="true">
          <div className="h-4 w-1/3 animate-pulse rounded bg-surface-soft" />
          <div className="h-40 w-full animate-pulse rounded-lg bg-surface-soft" />
          <div className="h-4 w-1/4 animate-pulse rounded bg-surface-soft" />
          <div className="h-24 w-full animate-pulse rounded-lg bg-surface-soft" />
        </div>
      )}

      {result && <AnswerCard result={result} />}
    </main>
  );
}

function AnswerCard({ result }: { result: AskResponse }) {
  return (
    <section className="mt-12 space-y-10">
      <div>
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
          <p className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
            Antwort
          </p>
          <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
            {result.llm_model} · {Math.round(result.elapsed_ms / 1000)}s
          </p>
        </div>
        <div className="rounded-lg border border-border-subtle bg-white p-8">
          <p className="whitespace-pre-wrap text-base leading-relaxed text-text-primary">
            {result.answer}
          </p>
        </div>
      </div>

      {result.sources.length > 0 && (
        <div>
          <p className="mb-4 mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
            Quellen · {result.sources.length}
          </p>
          <ol className="space-y-3">
            {result.sources.map((s, i) => (
              <SourceItem
                key={`${s.meeting_id}-${s.chunk_index}`}
                index={i + 1}
                source={s}
              />
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function SourceItem({ index, source }: { index: number; source: AskSource }) {
  return (
    <li className="rounded-lg border border-border-subtle bg-white p-6 transition hover:border-border-strong">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <span
            className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em]"
            style={{ color: "var(--gold-deep)" }}
          >
            [#{index}]
          </span>
          <Link
            href={`/m/${source.meeting_id}`}
            className="font-medium text-text-primary hover:underline"
          >
            {source.meeting_title}
          </Link>
        </div>
        <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
          Relevanz {Math.max(0, Math.round(source.score * 100))}%
        </p>
      </div>
      <p className="mt-1 text-[0.8125rem] text-text-meta">
        {formatMeetingDate(Date.parse(source.meeting_date))} · Abschnitt{" "}
        {source.chunk_index + 1}
      </p>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary">
        {source.content.length > 320
          ? source.content.slice(0, 320).trim() + " …"
          : source.content}
      </p>
    </li>
  );
}
