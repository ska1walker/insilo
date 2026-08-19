"use client";

/**
 * „Was verlässt diese Box?" — der Beleg hinter dem Nachweis in der
 * Navigation.
 *
 * Zeigt jedes konfigurierte Ziel einzeln, mit gemessener Menge statt
 * Zusicherung. Das ist die Ansicht, die Insilo gegenüber PLAUD, Otter
 * und Fireflies belegen kann: nicht „wir versprechen", sondern „hier
 * steht, was tatsächlich hinausging".
 */

import { ShieldAlert, ShieldCheck, Share2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { formatBytes } from "@/components/datenschutz-nachweis";
import { fetchEgress, type EgressRead } from "@/lib/api/egress";

export default function DatenschutzSeite() {
  const t = useTranslations("egress");
  const locale = useLocale();
  const [lage, setLage] = useState<EgressRead | null>(null);
  const [fehler, setFehler] = useState(false);

  useEffect(() => {
    fetchEgress().then(setLage).catch(() => setFehler(true));
  }, []);

  return (
    <main className="mx-auto max-w-[720px] px-6 py-10 md:px-12 md:py-16">
      <h1 className="text-2xl font-medium text-text-primaer">{t("titel")}</h1>

      {fehler ? (
        <div className="streifen streifen-hinweis mt-8">
          <span className="zeichen" aria-hidden>
            i
          </span>
          <span>{t("nichtGeladen")}</span>
        </div>
      ) : lage === null ? (
        <div className="mt-8 h-24 animate-pulse rounded-mittel bg-flaeche-1" />
      ) : (
        <>
          {/* Kernaussage — derselbe Zustand wie in der Navigation, nur
              ausführlich. */}
          {/* Audio zuerst: das ist das empfindlichste, was hinausgehen kann. */}
          {lage.stt_extern ? (
            <div className="streifen streifen-achtung mt-8">
              <span className="zeichen" aria-hidden>
                !
              </span>
              <span>
                <strong className="block">{t("sttExtern")}</strong>
                {lage.stt_host ? t("sttExternLang", { host: lage.stt_host }) : null}
              </span>
            </div>
          ) : lage.stt_eigene_box ? (
            <div className="streifen streifen-erfolg mt-8">
              <span className="zeichen" aria-hidden>
                ✓
              </span>
              <span>
                <strong className="block">{t("sttEigeneBox")}</strong>
                {lage.stt_host ? t("sttEigeneBoxLang", { host: lage.stt_host }) : null}
              </span>
            </div>
          ) : null}

          {lage.llm_extern ? (
            <div className="streifen streifen-achtung mt-8">
              <span className="zeichen" aria-hidden>
                !
              </span>
              <span>
                <strong className="block">{t("llmExtern")}</strong>
                {lage.llm_host
                  ? t("llmExternLang", { host: lage.llm_host })
                  : null}
              </span>
            </div>
          ) : lage.llm_eigene_box ? (
            <div className="streifen streifen-erfolg mt-8">
              <span className="zeichen" aria-hidden>
                ✓
              </span>
              <span>
                <strong className="block">{t("eigeneBox")}</strong>
                {lage.llm_host
                  ? t("eigeneBoxLang", { host: lage.llm_host })
                  : null}
              </span>
            </div>
          ) : lage.alles_bleibt ? (
            <div className="streifen streifen-erfolg mt-8">
              <span className="zeichen" aria-hidden>
                ✓
              </span>
              <span>
                <strong className="block">{t("allesBleibt")}</strong>
                {t("allesBleibtLang")}
              </span>
            </div>
          ) : (
            <div className="streifen streifen-hinweis mt-8">
              <span className="zeichen" aria-hidden>
                i
              </span>
              <span>
                <strong className="block">
                  {t("zieleAnzahl", { count: lage.ziele.length })}
                </strong>
                {lage.gesendete_bytes !== null
                  ? `${t("uebertragen", {
                      groesse: formatBytes(lage.gesendete_bytes, locale),
                    })} · ${t("zustellungen", { count: lage.zustellungen })}`
                  : t("nieGesendet")}
              </span>
            </div>
          )}

          {/* Die Ziele einzeln. Ohne Ziel keine Tabelle — ein leerer
              Rahmen behauptet Vollständigkeit, die er nicht belegt. */}
          {lage.ziele.length > 0 ? (
            <div className="tabelle-rahmen mt-8">
              <table className="am-tabelle">
                <tbody>
                  {lage.ziele.map((z, i) => (
                    <tr key={`${z.art}-${z.host}-${i}`}>
                      <td className="w-10">
                        {z.art === "llm" || z.art === "stt" ? (
                          <ShieldAlert
                            className="h-4 w-4 text-achtung"
                            strokeWidth={1.75}
                            aria-hidden
                          />
                        ) : (
                          <Share2
                            className="h-4 w-4 text-text-gedaempft"
                            strokeWidth={1.75}
                            aria-hidden
                          />
                        )}
                      </td>
                      <td>
                        <span className="block text-text-primaer">{z.host}</span>
                        <span className="text-[0.8125rem] text-text-gedaempft">
                          {z.art === "stt"
                            ? t("zielStt")
                            : z.art === "llm"
                              ? t("zielLlm")
                              : t("zielWebhook")}
                          {z.beschreibung ? ` · ${z.beschreibung}` : ""}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="leerzustand mt-8">
              <ShieldCheck className="mx-auto h-8 w-8" strokeWidth={1.5} aria-hidden />
              <h4>{t("allesBleibt")}</h4>
              <p>{t("allesBleibtLang")}</p>
            </div>
          )}
        </>
      )}
    </main>
  );
}
