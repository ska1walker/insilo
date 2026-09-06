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
import { formatBytes } from "@/lib/format";

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

  const { alles_bleibt, llm_extern, llm_eigene_box, llm_host, stt_extern, ziele, gesendete_bytes } =
    lage;

  // Die eigene Box unter öffentlicher Adresse ist kein Warnfall: das
  // Modell läuft hier, nur der Weg führt über das Netz. Sie bekommt den
  // Erfolgston, nennt aber den Host — verschwiegen wird nichts.
  // Ton, der die Box verlässt, wiegt schwerer als ein Transkript — er
  // steht deshalb vor allen anderen Fällen.
  const warnung = stt_extern || llm_extern;
  const ton = warnung ? "achtung" : alles_bleibt || llm_eigene_box ? "erfolg" : "neutral";
  const Icon = warnung ? ShieldAlert : alles_bleibt || llm_eigene_box ? ShieldCheck : Share2;

  // Kurzfassungen: die Navigationsspalte ist 220px breit und die Schrift
  // hier ist Mono. Die ausführlichen Sätze stehen auf der Detailseite,
  // erreichbar über denselben Klick.
  const kopf = stt_extern
    ? t("navStt")
    : llm_extern
    ? t("navLlm")
    : llm_eigene_box
      ? t("navEigeneBox")
      : alles_bleibt
        ? t("navBleibt")
        : t("navZiele", { count: ziele.length });

  const unterzeile = warnung || llm_eigene_box
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
      title={
        llm_host
          ? llm_extern
            ? t("llmExternLang", { host: llm_host })
            : t("eigeneBoxLang", { host: llm_host })
          : undefined
      }
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
