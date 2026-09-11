"use client";

import { ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import type { Summary } from "@/lib/api/meetings";

/**
 * Generic structured-summary renderer.
 * Walks the template-produced JSON tree and emits HubSpot-style sections —
 * because the schema varies per template (Mandantengespräch vs. Allgemein etc.)
 * we treat the content as a dict of typed fields and render each generically.
 *
 * Field labels live in `frontend/messages/{locale}.json` under the
 * `summaryLabels` namespace (v0.1.46+). The JSON schema keys themselves
 * stay German — only the user-facing display label is localized. If a
 * key isn't covered by `summaryLabels` (e.g. an org-custom field) we
 * fall back to a title-cased version of the key itself.
 */

/**
 * Welches Feld eines Objekts der Satz ist, und nicht die Randangabe.
 *
 * Gegenstück zu `_TASK_OBJECT_KEYS` in
 * `backend/app/exports/markdown.py` — die Markdown-Datei baut aus
 * denselben Feldern ihre Häkchenliste. Wer hier etwas ergänzt, ergänzt
 * es dort; ein Test hält die beiden zusammen.
 */
const TAT_FELDER = [
  "beschluss",
  "aufgabe",
  "task",
  "naechster_schritt",
  "schritt",
  "aussage",
  "text",
] as const;

function isEmpty(v: unknown): boolean {
  if (v === null || v === undefined) return true;
  if (typeof v === "string") return v.trim() === "";
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
}

/** Title-case a snake_case key as a last-resort fallback. */
function titleCaseKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Hook returning a `humanLabel(key)` that consults the `summaryLabels`
 * namespace and falls back to title-cased snake_case when a key is
 * unknown (e.g. user-defined custom fields).
 *
 * next-intl v4 exposes `t.has(key)`; we use it to avoid throwing on
 * missing keys.
 */
function useHumanLabel(): (key: string) => string {
  const t = useTranslations("summaryLabels");
  return (key: string) => (t.has(key) ? t(key) : titleCaseKey(key));
}

export function SummaryView({ summary }: { summary: Summary }) {
  const t = useTranslations("summary");
  const humanLabel = useHumanLabel();
  // Felder mit `_`-Präfix (z. B. `_analyse`) sind LLM-interne
  // Scratch-Felder seit v0.1.40 (CoT-vor-Output-Pattern). Sie werden
  // separat als ausklappbare „LLM-Überlegungen" gerendert, damit der
  // Hauptkörper sauber bleibt.
  const all = Object.entries(summary.content);
  const internalEntries = all.filter(
    ([k, v]) => k.startsWith("_") && !isEmpty(v),
  );
  const entries = all.filter(
    ([k, v]) => !k.startsWith("_") && !isEmpty(v),
  );

  // Welche Felder oben stehen, entscheidet das Backend
  // (`exports/markdown.sortieren`) — eine Stelle für Ansicht und Datei.
  // Ohne die Angabe steht alles oben: eine ältere Antwort soll nichts
  // verstecken, das sie nicht einordnen kann.
  const vorhanden = new Map(entries);
  const kopfNamen = (summary.kopf ?? entries.map(([k]) => k)).filter((k) =>
    vorhanden.has(k),
  );
  const mehrNamen = (summary.mehr ?? []).filter((k) => vorhanden.has(k));

  if (entries.length === 0 && internalEntries.length === 0) {
    return <p className="text-sm text-text-gedaempft">{t("emptyExtract")}</p>;
  }

  return (
    <div className="space-y-8">
      {kopfNamen.map((key) => (
        <SummarySection
          key={key}
          keyName={key}
          value={vorhanden.get(key)}
          humanLabel={humanLabel}
        />
      ))}

      {mehrNamen.length > 0 && (
        <details className="group border-t border-trennlinie pt-6">
          <summary className="mono flex cursor-pointer select-none items-center gap-2 text-xs uppercase tracking-[0.08em] text-text-gedaempft hover:text-text-primaer">
            <ChevronRight
              size={14}
              aria-hidden
              className="transition-transform group-open:rotate-90"
            />
            {t("mehrZeigen")}
            <span className="normal-case tracking-normal">
              · {t("mehrAnzahl", { n: mehrNamen.length })}
            </span>
          </summary>
          <div className="mt-6 space-y-8">
            {mehrNamen.map((key) => (
              <SummarySection
                key={key}
                keyName={key}
                value={vorhanden.get(key)}
                humanLabel={humanLabel}
              />
            ))}
          </div>
        </details>
      )}

      {internalEntries.length > 0 && (
        <details className="group border-t border-trennlinie pt-6 text-sm">
          <summary className="cursor-pointer select-none text-text-gedaempft hover:text-text-primaer">
            {t("internalThoughts")}
          </summary>
          <div className="mt-3 space-y-3 rounded-md bg-flaeche-1 p-3 text-xs leading-relaxed text-text-sekundaer">
            {internalEntries.map(([key, value]) => (
              <div key={key}>
                <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-gedaempft">
                  {humanLabel(key.replace(/^_/, ""))}
                </p>
                <p className="mt-1">{String(value)}</p>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function SummarySection({
  keyName,
  value,
  humanLabel,
}: {
  keyName: string;
  value: unknown;
  humanLabel: (key: string) => string;
}) {
  return (
    <section>
      <h3 className="mb-3 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-gedaempft">
        {humanLabel(keyName)}
      </h3>
      <SummaryValue value={value} humanLabel={humanLabel} />
    </section>
  );
}

function SummaryValue({
  value,
  humanLabel,
}: {
  value: unknown;
  humanLabel: (key: string) => string;
}) {
  if (value === null || value === undefined) return null;

  if (typeof value === "string") {
    return <p className="text-base leading-relaxed text-text-primaer">{value}</p>;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return <p className="text-base text-text-primaer">{String(value)}</p>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return null;

    // Array of strings → bullet list
    if (value.every((v) => typeof v === "string")) {
      return (
        <ul className="space-y-1 pl-5 [&>li]:list-disc [&>li]:marker:text-text-gedaempft">
          {(value as string[]).map((v, i) => (
            <li key={i} className="text-base leading-relaxed text-text-primaer">
              {v}
            </li>
          ))}
        </ul>
      );
    }

    // Array of objects → key/value sub-cards
    return (
      <div className="space-y-3">
        {value.map((item, i) => (
          <div
            key={i}
            className="rounded-md border border-trennlinie bg-flaeche-1 p-4"
          >
            <SummaryValue value={item} humanLabel={humanLabel} />
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).filter(
      ([, v]) => !isEmpty(v),
    );
    if (entries.length === 0) return null;

    // Ein Beschluss führt mit dem Beschluss, nicht mit der Frist.
    //
    // `jsonb` behält die Reihenfolge der Schlüssel **nicht** — Postgres
    // sortiert nach Länge, also steht `frist` (5) vor `beschluss` (9)
    // und `verantwortlich` (14) dahinter. Auf der Box gesehen:
    // „Frist 15.10.2026 · Beschluss Frist zur Zahlung setzen". Solange
    // das unter „Mehr" lag, fiel es niemandem auf; seit die Beschlüsse
    // oben stehen, ist es das Erste, was jemand liest.
    const satz = TAT_FELDER.find((k) => typeof (value as Record<string, unknown>)[k] === "string");
    if (satz) {
      const rest = entries.filter(([k]) => k !== satz);
      return (
        <div>
          <p className="text-base leading-relaxed text-text-primaer">
            {String((value as Record<string, unknown>)[satz])}
          </p>
          {rest.length > 0 && (
            <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[0.8125rem] text-text-gedaempft">
              {rest.map(([k, v]) => (
                <span key={k}>
                  {humanLabel(k)}: <span className="text-text-sekundaer">{String(v)}</span>
                </span>
              ))}
            </p>
          )}
        </div>
      );
    }

    return (
      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-[180px_1fr]">
        {entries.map(([k, v]) => (
          <div key={k} className="md:contents">
            <dt className="text-[0.8125rem] font-medium text-text-gedaempft md:py-1">
              {humanLabel(k)}
            </dt>
            <dd className="md:py-1">
              <SummaryValue value={v} humanLabel={humanLabel} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return null;
}
