"use client";

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

  if (entries.length === 0 && internalEntries.length === 0) {
    return <p className="text-sm text-text-meta">{t("emptyExtract")}</p>;
  }

  return (
    <div className="space-y-8">
      {entries.map(([key, value]) => (
        <SummarySection
          key={key}
          keyName={key}
          value={value}
          humanLabel={humanLabel}
        />
      ))}

      {internalEntries.length > 0 && (
        <details className="group border-t border-border-subtle pt-6 text-sm">
          <summary className="cursor-pointer select-none text-text-meta hover:text-text-primary">
            {t("internalThoughts")}
          </summary>
          <div className="mt-3 space-y-3 rounded-md bg-surface-soft p-3 text-xs leading-relaxed text-text-secondary">
            {internalEntries.map(([key, value]) => (
              <div key={key}>
                <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
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
      <h3 className="mb-3 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
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
    return <p className="text-base leading-relaxed text-text-primary">{value}</p>;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return <p className="text-base text-text-primary">{String(value)}</p>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return null;

    // Array of strings → bullet list
    if (value.every((v) => typeof v === "string")) {
      return (
        <ul className="space-y-1 pl-5 [&>li]:list-disc [&>li]:marker:text-text-meta">
          {(value as string[]).map((v, i) => (
            <li key={i} className="text-base leading-relaxed text-text-primary">
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
            className="rounded-md border border-border-subtle bg-surface-soft p-4"
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
    return (
      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-[180px_1fr]">
        {entries.map(([k, v]) => (
          <div key={k} className="md:contents">
            <dt className="text-[0.8125rem] font-medium text-text-meta md:py-1">
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
