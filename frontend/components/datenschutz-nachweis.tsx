"use client";

/**
 * Der Datenschutz-Nachweis am unteren Rand der Navigation.
 *
 * Das AImighty-Designsystem sieht ihn dort vor — „mit gemessenen Werten
 * oder gar nicht". Deshalb steht hier nichts, solange der Zustand nicht
 * abrufbar ist: eine Zusage ohne Beleg wäre schlimmer als gar keine.
 *
 * Drei Lagen:
 *   alles intern   → Erfolgston, „Alles bleibt auf dieser Box"
 *   Ziele aktiv    → neutral, Anzahl und übertragene Menge
 *   LLM extern     → Achtungston; hier verlassen vollständige
 *                    Transkripte das Haus, das muss man sehen
 *
 * Farbe trägt die Aussage nie allein — jede Lage hat Zeichen und Satz,
 * wie das Paket es für Zustandsmeldungen verlangt.
 */

import { ShieldAlert, ShieldCheck, Share2 } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchEgress, type EgressRead } from "@/lib/api/egress";

/** Byte-Größe in DIN-gerechter Schreibweise (Komma als Dezimaltrenner). */
export function formatBytes(bytes: number, locale: string): string {
  if (bytes < 1024) return `${bytes} B`;
  const einheiten = ["kB", "MB", "GB"];
  let wert = bytes / 1024;
  let i = 0;
  while (wert >= 1024 && i < einheiten.length - 1) {
    wert /= 1024;
    i++;
  }
  const gerundet = wert < 10 ? Math.round(wert * 10) / 10 : Math.round(wert);
  return `${gerundet.toLocaleString(locale)} ${einheiten[i]}`;
}

export function DatenschutzNachweis({ locale }: { locale: string }) {
  const t = useTranslations("egress");
  const [lage, setLage] = useState<EgressRead | null>(null);
  const [fehlgeschlagen, setFehlgeschlagen] = useState(false);

  useEffect(() => {
    let abgebrochen = false;
    fetchEgress()
      .then((l) => !abgebrochen && setLage(l))
      .catch(() => !abgebrochen && setFehlgeschlagen(true));
    return () => {
      abgebrochen = true;
    };
  }, []);

  // Nicht messbar heißt: nichts behaupten. Der Platz bleibt leer.
  if (fehlgeschlagen || lage === null) return null;

  const { alles_bleibt, llm_extern, llm_host, ziele, gesendete_bytes } = lage;

  const ton = llm_extern ? "achtung" : alles_bleibt ? "erfolg" : "neutral";
  const Icon = llm_extern ? ShieldAlert : alles_bleibt ? ShieldCheck : Share2;

  // Kurzfassungen: die Navigationsspalte ist 220px breit und die Schrift
  // hier ist Mono. Die ausführlichen Sätze stehen auf der Detailseite,
  // erreichbar über denselben Klick.
  const kopf = llm_extern
    ? t("navLlm")
    : alles_bleibt
      ? t("navBleibt")
      : t("navZiele", { count: ziele.length });

  const unterzeile = llm_extern
    ? llm_host
    : alles_bleibt
      ? null
      : gesendete_bytes !== null
        ? t("uebertragen", { groesse: formatBytes(gesendete_bytes, locale) })
        : t("nieGesendet");

  return (
    <Link
      href="/datenschutz"
      className={`huelle-schutz huelle-schutz-${ton}`}
      title={llm_extern && llm_host ? t("llmExternLang", { host: llm_host }) : undefined}
    >
      <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden />
      <span className="huelle-schutz-text">
        <span className="huelle-schutz-kopf">{kopf}</span>
        {unterzeile ? (
          <span className="huelle-schutz-unter">{unterzeile}</span>
        ) : null}
      </span>
    </Link>
  );
}
