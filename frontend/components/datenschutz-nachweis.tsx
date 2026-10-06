"use client";

/**
 * Der Datenschutz-Nachweis auf „Über Insilo“ (bis 0.1.105 am Fuß der
 * Navigation; den Fuß gibt es seit CI G8 in keiner App mehr).
 *
 * „Mit gemessenen Werten oder gar nicht": Solange der Zustand nicht
 * abrufbar ist, steht hier nichts — eine Zusage ohne Beleg wäre schlimmer
 * als gar keine.
 *
 * Drei Lagen (ABGLEICH IN-B4, CSS in IN-NACHWEIS):
 *   alles intern   → leise, Zeichen `lokal`, „Alles bleibt auf dieser Box"
 *   Ziele aktiv    → `data-extern`, Zeichen `weitergabe` in Gold, Anzahl
 *                    und übertragene Menge
 *   LLM/STT extern → `data-zustand="achtung"`; hier verlassen vollständige
 *                    Transkripte oder der Ton das Haus, das muss man sehen
 *
 * Farbe trägt die Aussage nie allein — jede Lage hat Zeichen und Satz,
 * wie das Paket es für Zustandsmeldungen verlangt.
 */

import { AlertTriangle, Lokal, Share2 } from "@/lib/symbole";
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
  const Icon = warnung ? AlertTriangle : alles_bleibt || llm_eigene_box ? Lokal : Share2;

  // Kurzfassungen; die ausführlichen Sätze stehen auf der Detailseite
  // /datenschutz, erreichbar über denselben Klick.
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
      className="nachweis"
      data-zustand={warnung ? "achtung" : undefined}
      data-extern={!warnung && !alles_bleibt && !llm_eigene_box ? "true" : undefined}
      title={
        llm_host
          ? llm_extern
            ? t("llmExternLang", { host: llm_host })
            : t("eigeneBoxLang", { host: llm_host })
          : undefined
      }
    >
      <Icon size={16} aria-hidden />
      <span className="nachweis-text">
        <span>{kopf}</span>
        {unterzeile ? <span className="nachweis-unter">{unterzeile}</span> : null}
      </span>
    </Link>
  );
}
