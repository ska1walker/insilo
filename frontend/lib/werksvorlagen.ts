"use client";

import { useLocale, useTranslations } from "next-intl";

/**
 * Die fünf Werksvorlagen in der Sprache der Oberfläche.
 *
 * Name und Beschreibung stehen in der Datenbank nur auf Deutsch
 * (supabase/seed.sql). Übersetzt wird hier, über messages/*.json
 * (`werksvorlagen.<kürzel>`), nach Kennung — nicht nach Name. Hat eine
 * Organisation einer Werksvorlage eine eigene Bezeichnung gegeben
 * (`display_name`/`display_description`), gilt die, in jeder Sprache.
 */
export const WERKSVORLAGEN: Record<string, string> = {
  "00000000-0000-0000-0000-000000000001": "allgemein",
  "00000000-0000-0000-0000-000000000002": "mandant",
  "00000000-0000-0000-0000-000000000003": "vertrieb",
  "00000000-0000-0000-0000-000000000004": "jahresgespraech",
  "00000000-0000-0000-0000-000000000005": "schnellnotiz",
};

type Vorlage = {
  id: string;
  name: string;
  description: string | null;
  display_name?: string | null;
  display_description?: string | null;
};

export function useWerksvorlagen() {
  const t = useTranslations("werksvorlagen");
  const locale = useLocale();

  /** Der Werksname in der Sprache der Oberfläche, sonst der gespeicherte. */
  function standardName(id: string | null | undefined, sonst: string): string {
    const k = id ? WERKSVORLAGEN[id] : undefined;
    return k ? t(`${k}.name`) : sonst;
  }

  function standardBeschreibung(id: string | null | undefined, sonst: string | null): string | null {
    const k = id ? WERKSVORLAGEN[id] : undefined;
    return k ? t(`${k}.beschreibung`) : sonst;
  }

  const name = (v: Vorlage) => v.display_name || standardName(v.id, v.name);

  return {
    standardName,
    standardBeschreibung,
    /** Was die Oberfläche zeigt: eigene Bezeichnung vor Werksname. */
    name,
    beschreibung: (v: Vorlage) => v.display_description || standardBeschreibung(v.id, v.description),
    /**
     * Wie das Backend ordnet (Werksvorlagen zuerst, dann nach Name) — aber
     * nach dem Namen, der zu sehen ist, nicht nach dem deutschen.
     */
    sortiert: <T extends Vorlage & { is_system: boolean }>(liste: T[]): T[] =>
      [...liste].sort(
        (a, b) => Number(b.is_system) - Number(a.is_system) || name(a).localeCompare(name(b), locale),
      ),
  };
}
