"use client";

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
          setError("Die KI-Dienste sind gerade nicht erreichbar. Bitte gleich erneut versuchen.");
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
      <h1 className="text-3xl font-medium md:text-4xl">Frag dein Meeting-Archiv</h1>
      <p className="mt-3 max-w-[640px] text-text-secondary">
        Stellen Sie eine Frage in natürlicher Sprache. Insilo durchsucht die
        Transkripte und Zusammenfassungen aller Besprechungen Ihrer Organisation
        und antwortet mit Quellenangaben.
      </p>

      <form
        className="mt-10"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <div className="flex flex-col gap-3 md:flex-row">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="z. B. Welche Beschlüsse sind in der letzten Beirats-Besprechung gefasst worden?"
            rows={2}
            className="input min-h-[88px] flex-1 resize-none"
            disabled={phase === "asking"}
          />
          <button
            type="submit"
            className="btn-primary self-start md:self-stretch md:min-w-[140px]"
            disabled={phase === "asking" || question.trim().length < 4}
          >
            {phase === "asking" ? "Suche …" : "Fragen"}
          </button>
        </div>

        {phase === "idle" && (
          <div className="mt-6 flex flex-wrap gap-2">
            <span className="mono mr-1 text-xs uppercase tracking-[0.08em] text-text-meta">
              Beispiele:
            </span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  setQuestion(ex);
                  submit(ex);
                }}
                className="btn-tertiary text-sm"
              >
                {ex}
              </button>
            ))}
          </div>
        )}
      </form>

      {error && (
        <div className="mt-10 rounded-lg border border-border-subtle bg-white p-6">
          <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-recording">
            Fehler
          </p>
          <p className="mt-2 text-sm text-text-secondary">{error}</p>
        </div>
      )}

      {phase === "asking" && (
        <div className="mt-10 space-y-3">
          <div className="h-6 w-1/3 animate-pulse rounded bg-surface-soft" />
          <div className="h-32 w-full animate-pulse rounded-lg bg-surface-soft" />
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
          <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
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
          <p className="mb-4 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
            Quellen ({result.sources.length})
          </p>
          <ol className="space-y-3">
            {result.sources.map((s, i) => (
              <SourceItem key={`${s.meeting_id}-${s.chunk_index}`} index={i + 1} source={s} />
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function SourceItem({ index, source }: { index: number; source: AskSource }) {
  return (
    <li className="rounded-lg border border-border-subtle bg-white p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <span
            className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em]"
            style={{ color: "var(--gold)" }}
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
        {formatMeetingDate(Date.parse(source.meeting_date))} · Abschnitt {source.chunk_index + 1}
      </p>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary">
        {source.content.length > 320
          ? source.content.slice(0, 320).trim() + " …"
          : source.content}
      </p>
    </li>
  );
}
