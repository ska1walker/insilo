"use client";

import { useTranslations } from "next-intl";
import type { Summary } from "@/lib/api/meetings";

/**
 * Generic structured-summary renderer.
 * Walks the template-produced JSON tree and emits HubSpot-style sections —
 * because the schema varies per template (Mandantengespräch vs. Allgemein etc.)
 * we treat the content as a dict of typed fields and render each generically.
 */

const LABEL_OVERRIDES: Record<string, string> = {
  // Default schema for user-created templates (since v0.1.25)
  zusammenfassung: "Zusammenfassung",
  kernpunkte: "Kernpunkte",
  entscheidungen: "Entscheidungen",
  aufgaben: "Aufgaben",
  was: "Was",
  wer: "Wer",
  wann: "Wann",
  // Existing seed templates
  anwesende: "Anwesende",
  kernthemen: "Kernthemen",
  wichtige_aussagen: "Wichtige Aussagen",
  beschluesse: "Beschlüsse",
  offene_fragen: "Offene Fragen",
  naechste_schritte: "Nächste Schritte",
  mandantenname: "Mandant",
  sachverhalt: "Sachverhalt",
  rechtsfragen: "Rechtsfragen",
  eingebrachte_unterlagen: "Eingebrachte Unterlagen",
  vereinbarte_leistungen: "Vereinbarte Leistungen",
  wichtige_termine_fristen: "Termine & Fristen",
  honorarvereinbarung: "Honorar",
  naechste_schritte_mandat: "Nächste Schritte (Mandat)",
  verschwiegenheitsvermerke: "Schweigepflicht-Vermerke",
  kunde: "Kunde",
  schmerzpunkte: "Schmerzpunkte",
  aktuelle_loesung: "Aktuelle Lösung",
  bant: "BANT-Einschätzung",
  einwaende: "Einwände",
  vereinbarte_naechste_schritte: "Nächste Schritte",
  follow_up_datum: "Follow-up",
  verkaufschance_einschaetzung: "Chance",
  bestandsuebersicht: "Bestandsübersicht",
  risikoveraenderungen: "Risikoveränderungen",
  cross_selling_potenziale: "Cross-Selling-Potenziale",
  kundenwuensche: "Kundenwünsche",
  wiedervorlage: "Wiedervorlage",
  beschluss: "Beschluss",
  verantwortlich: "Verantwortlich",
  frist: "Frist",
  sprecher: "Sprecher",
  aussage: "Aussage",
  termin: "Termin",
  budget: "Budget",
  entscheider: "Entscheider",
  need: "Bedarf",
  timing: "Timing",
};

function humanLabel(key: string): string {
  return (
    LABEL_OVERRIDES[key] ??
    key
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function isEmpty(v: unknown): boolean {
  if (v === null || v === undefined) return true;
  if (typeof v === "string") return v.trim() === "";
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
}

export function SummaryView({ summary }: { summary: Summary }) {
  const t = useTranslations("summary");
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
        <SummarySection key={key} keyName={key} value={value} />
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

function SummarySection({ keyName, value }: { keyName: string; value: unknown }) {
  return (
    <section>
      <h3 className="mb-3 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
        {humanLabel(keyName)}
      </h3>
      <SummaryValue value={value} />
    </section>
  );
}

function SummaryValue({ value }: { value: unknown }) {
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
            <SummaryValue value={item} />
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
              <SummaryValue value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return null;
}
