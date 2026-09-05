"use client";

/**
 * Protokoll — wer hat wann was geändert oder ausgeleitet.
 *
 * Das Gegenstück zum Datenschutz-Nachweis: der misst, *wie viel* die Box
 * verlassen hat, dieses hier sagt, *wer es veranlasst hat*. Zusammen sind
 * das die zwei Fragen, die ein Datenschutzbeauftragter in einer Kanzlei
 * stellt.
 *
 * `public.audit_log` lag seit Migration 0001 bereit und wurde bis v0.1.81
 * von keiner Zeile Code beschrieben, während CLAUDE.md „jede
 * Datenänderung wird geloggt" versprach.
 */

import { ArrowLeft, KeyRound, Share2, User } from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import {
  fetchProtokoll,
  type ProtokollEintrag,
  type ProtokollSeite,
} from "@/lib/api/protokoll";

const SEITENGROESSE = 50;

type Lage =
  | { art: "laedt" }
  | { art: "ok"; seite: ProtokollSeite; eintraege: ProtokollEintrag[] }
  | { art: "fehler" };

export default function ProtokollSeiteAnsicht() {
  const t = useTranslations("protokoll");
  const locale = useLocale();
  const [lage, setLage] = useState<Lage>({ art: "laedt" });
  const [nurAusleitung, setNurAusleitung] = useState(false);
  const [laedtMehr, setLaedtMehr] = useState(false);

  const laden = useCallback(async () => {
    setLage({ art: "laedt" });
    try {
      const seite = await fetchProtokoll({ nurAusleitung, anzahl: SEITENGROESSE });
      setLage({ art: "ok", seite, eintraege: seite.eintraege });
    } catch {
      setLage({ art: "fehler" });
    }
  }, [nurAusleitung]);

  useEffect(() => {
    laden();
  }, [laden]);

  async function mehr() {
    if (lage.art !== "ok") return;
    setLaedtMehr(true);
    try {
      const weiter = await fetchProtokoll({
        nurAusleitung,
        anzahl: SEITENGROESSE,
        ab: lage.eintraege.length,
      });
      setLage({
        art: "ok",
        seite: weiter,
        eintraege: [...lage.eintraege, ...weiter.eintraege],
      });
    } catch {
      /* Die bereits geladenen Einträge bleiben stehen. */
    } finally {
      setLaedtMehr(false);
    }
  }

  return (
    <main className="mx-auto max-w-[1280px] px-6 py-10 md:px-12 md:py-16">
      <Link
        href="/datenschutz"
        className="mono inline-flex items-center gap-2 text-xs uppercase tracking-[0.08em] text-text-gedaempft hover:text-text-primaer"
      >
        <ArrowLeft size={14} aria-hidden />
        {t("zurueck")}
      </Link>

      <h1 className="mb-4 mt-4 text-3xl font-medium md:text-4xl">{t("titel")}</h1>
      <p className="max-w-[720px] text-text-sekundaer">{t("einleitung")}</p>

      {lage.art === "ok" && !lage.seite.darf_alles_sehen && (
        <div className="streifen streifen-hinweis mt-6 max-w-[720px]">
          <span className="zeichen" aria-hidden>
            i
          </span>
          <span>{t("nurEigene")}</span>
        </div>
      )}

      {/* Filter. Nur einer — die Frage, die im Ernstfall gestellt wird,
          lautet „was hat die Box verlassen", nicht „zeig mir Etiketten". */}
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setNurAusleitung(false)}
          aria-pressed={!nurAusleitung}
          className={`btn ${nurAusleitung ? "btn-sekundaer" : "btn-primaer"}`}
        >
          {t("alleVorgaenge")}
        </button>
        <button
          type="button"
          onClick={() => setNurAusleitung(true)}
          aria-pressed={nurAusleitung}
          className={`btn inline-flex items-center gap-2 ${
            nurAusleitung ? "btn-primaer" : "btn-sekundaer"
          }`}
        >
          <Share2 size={16} aria-hidden />
          {t("nurAusleitung")}
        </button>
        {nurAusleitung && (
          <p className="text-[0.8125rem] text-text-gedaempft">
            {t("nurAusleitungHinweis")}
          </p>
        )}
      </div>

      {lage.art === "laedt" && (
        <div className="mt-8 space-y-2" aria-live="polite" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-14 animate-pulse rounded-mittel bg-flaeche-1" />
          ))}
        </div>
      )}

      {lage.art === "fehler" && (
        <div className="streifen streifen-fehler mt-8">
          <span className="zeichen" aria-hidden>
            !
          </span>
          <span>{t("nichtGeladen")}</span>
        </div>
      )}

      {lage.art === "ok" && lage.eintraege.length === 0 && (
        <div className="mt-8 rounded-lg border border-trennlinie bg-seite p-12 text-center">
          <p className="font-display text-xl font-medium">{t("leer")}</p>
          <p className="mx-auto mt-3 max-w-[460px] text-text-sekundaer">
            {nurAusleitung ? t("leerGefiltert") : t("leerHinweis")}
          </p>
        </div>
      )}

      {lage.art === "ok" && lage.eintraege.length > 0 && (
        <>
          <div className="tabelle-rahmen mt-8 overflow-x-auto">
            <table className="am-tabelle w-full">
              <thead>
                <tr>
                  <th scope="col">{t("spalteZeit")}</th>
                  <th scope="col">{t("spalteVorgang")}</th>
                  <th scope="col">{t("spalteUrheber")}</th>
                  <th scope="col">{t("spalteGegenstand")}</th>
                </tr>
              </thead>
              <tbody>
                {lage.eintraege.map((e) => (
                  <Zeile key={e.id} eintrag={e} locale={locale} />
                ))}
              </tbody>
            </table>
          </div>

          {lage.seite.hat_mehr && (
            <button
              type="button"
              onClick={mehr}
              disabled={laedtMehr}
              className="btn btn-sekundaer mt-6 inline-flex"
            >
              {laedtMehr ? t("laedt") : t("mehrLaden")}
            </button>
          )}
        </>
      )}
    </main>
  );
}

/**
 * Was der Endpunkt über den Gegenstand nachgereicht hat.
 *
 * Die Middleware liest die Kennung am Pfad ab — bei einer Neuanlage gibt
 * der Pfad sie nicht her, also legt der Endpunkt Name oder Ziel dazu
 * (`audit.ergaenze`). Nur diese drei Felder, damit hier nicht beliebiger
 * Inhalt in die Ansicht rutscht.
 */
function nachtrag(eintrag: ProtokollEintrag): string | null {
  for (const feld of ["titel", "name", "ziel"] as const) {
    const wert = eintrag.zusatz?.[feld];
    if (typeof wert === "string" && wert.trim()) return wert;
  }
  return null;
}

function Zeile({ eintrag, locale }: { eintrag: ProtokollEintrag; locale: string }) {
  const t = useTranslations("protokoll");
  const schluessel = `aktionen.${eintrag.aktion.replace(/\./g, "_")}`;
  // Ein Vorgang, den die Oberfläche noch nicht kennt, soll die Zeile
  // nicht sprengen — dann steht der technische Name da. Besser ein
  // unschöner Eintrag als ein fehlender.
  const bezeichnung = t.has(schluessel) ? t(schluessel) : eintrag.aktion;

  return (
    <tr>
      <td className="mono whitespace-nowrap text-[0.8125rem] text-text-gedaempft">
        {new Date(eintrag.zeitpunkt).toLocaleString(locale, {
          dateStyle: "short",
          timeStyle: "short",
        })}
      </td>
      <td>
        <span className="flex flex-wrap items-center gap-2">
          <span className="text-text-primaer">{bezeichnung}</span>
          {eintrag.ausleitung && (
            // Zeichen und Wort, nicht nur Farbe.
            <span className="inline-flex items-center gap-1 rounded-voll border border-rand px-2 py-0.5 text-[0.6875rem] uppercase tracking-[0.06em] text-text-sekundaer">
              <Share2 size={11} aria-hidden />
              {t("ausleitungMarke")}
            </span>
          )}
          {!eintrag.erfolg && (
            <span className="inline-flex items-center gap-1 text-[0.75rem] text-text-sekundaer">
              <span aria-hidden>✕</span>
              {t("fehlgeschlagen")}
            </span>
          )}
        </span>
      </td>
      <td className="whitespace-nowrap text-[0.8125rem]">
        <span className="inline-flex items-center gap-2 text-text-sekundaer">
          {eintrag.urheber_art === "api_key" ? (
            <KeyRound size={13} aria-hidden />
          ) : (
            <User size={13} aria-hidden />
          )}
          {eintrag.urheber ?? t("unbekannterUrheber")}
          {eintrag.urheber_art === "api_key" && (
            <span className="text-text-gedaempft">({t("ueberSchluessel")})</span>
          )}
        </span>
      </td>
      <td className="text-[0.8125rem] text-text-sekundaer">
        {eintrag.bezeichnung ? (
          // Nur Besprechungen haben eine Detailansicht, auf die sich
          // verweisen lässt.
          <Link href={`/m/${eintrag.kennung}`} className="hover:text-text-primaer">
            {eintrag.bezeichnung}
          </Link>
        ) : nachtrag(eintrag) ? (
          // Aus dem Nachtrag des Endpunkts: der Name des
          // Zugriffsschlüssels, das Ziel eines Webhooks. Ohne das stünde
          // ausgerechnet bei den Vorgängen „—", bei denen die Frage nach
          // dem Gegenstand am ehesten gestellt wird.
          nachtrag(eintrag)
        ) : eintrag.art === "meeting" && eintrag.kennung ? (
          <span className="text-text-gedaempft">{t("entfernt")}</span>
        ) : (
          <span className="text-text-gedaempft">—</span>
        )}
      </td>
    </tr>
  );
}
