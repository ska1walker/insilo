"use client";

/**
 * Papierkorb — was gelöscht wurde und noch zurückgeholt werden kann.
 *
 * Bis v0.1.81 gab es diese Ansicht nicht, und es hätte auch nichts zu
 * zeigen gegeben: das Löschen setzte `deleted_at` und entfernte die
 * Tonaufnahme im selben Atemzug. Die „30-Tage-Frist vor Hard-Delete" aus
 * CLAUDE.md galt damit für eine Zeile, deren Inhalt schon weg war.
 *
 * Zwei Fristen laufen hier nebeneinander und bedeuten Verschiedenes:
 * die Papierkorb-Frist entfernt die Besprechung ganz, die
 * Aufbewahrungsfrist nur die Tonaufnahme. Deshalb kann ein Eintrag hier
 * stehen und schon keine Aufnahme mehr haben.
 */

import { ArrowLeft, RotateCcw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { StatusPill } from "@/components/status-pill";
import { useToast } from "@/components/toast";
import {
  fetchPapierkorb,
  purgeMeeting,
  restoreMeeting,
  type Papierkorb,
  type PapierkorbEintrag,
} from "@/lib/api/meetings";
import { formatDuration, formatMeetingDate } from "@/lib/format";

type Lage =
  | { art: "laedt" }
  | { art: "ok"; papierkorb: Papierkorb }
  | { art: "fehler" };

export default function PapierkorbSeite() {
  const t = useTranslations("papierkorb");
  const locale = useLocale();
  const toast = useToast();
  const [lage, setLage] = useState<Lage>({ art: "laedt" });
  // Welcher Eintrag gerade nach Bestätigung fragt. Endgültiges Löschen
  // ist der einzige Weg hier, der nicht rückgängig zu machen ist — der
  // bekommt eine Rückfrage im Zusammenhang, keinen Systemdialog.
  const [fragt, setFragt] = useState<string | null>(null);
  const [arbeitet, setArbeitet] = useState<string | null>(null);

  const laden = useCallback(async () => {
    try {
      setLage({ art: "ok", papierkorb: await fetchPapierkorb() });
    } catch {
      setLage({ art: "fehler" });
    }
  }, []);

  useEffect(() => {
    laden();
  }, [laden]);

  async function zurueckholen(eintrag: PapierkorbEintrag) {
    setArbeitet(eintrag.id);
    try {
      await restoreMeeting(eintrag.id);
      await laden();
      toast.show({ message: t("zurueckholen"), variant: "success" });
    } catch {
      toast.show({ message: t("fehler"), variant: "error" });
    } finally {
      setArbeitet(null);
    }
  }

  async function endgueltig(eintrag: PapierkorbEintrag) {
    setArbeitet(eintrag.id);
    try {
      await purgeMeeting(eintrag.id);
      await laden();
      toast.show({ message: t("endgueltigLoeschen"), variant: "success" });
    } catch {
      toast.show({ message: t("fehler"), variant: "error" });
    } finally {
      setArbeitet(null);
      setFragt(null);
    }
  }

  const eintraege = lage.art === "ok" ? lage.papierkorb.eintraege : [];

  return (
    <main className="mx-auto max-w-[1280px] px-6 py-10 md:px-12 md:py-16">
      <Link
        href="/besprechungen"
        className="mono inline-flex items-center gap-2 text-xs uppercase tracking-[0.08em] text-text-gedaempft hover:text-text-primaer"
      >
        <ArrowLeft size={14} aria-hidden />
        {t("zurueck")}
      </Link>

      <div className="mb-6 mt-4 flex items-baseline justify-between gap-4">
        <h1 className="text-3xl font-medium md:text-4xl">{t("titel")}</h1>
        {eintraege.length > 0 && (
          <p className="mono shrink-0 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
            {t("anzahl", { n: eintraege.length })}
          </p>
        )}
      </div>

      <p className="max-w-[640px] text-text-sekundaer">{t("einleitung")}</p>

      {lage.art === "ok" && (
        <p className="mono mt-3 text-[0.8125rem] text-text-gedaempft">
          {lage.papierkorb.frist_tage > 0
            ? t("frist", { tage: lage.papierkorb.frist_tage })
            : t("fristAus")}
        </p>
      )}

      {lage.art === "laedt" && (
        <div className="mt-8 space-y-3" aria-live="polite" aria-busy="true">
          {[0, 1].map((i) => (
            <div key={i} className="h-[88px] rounded-lg bg-flaeche-3" />
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

      {lage.art === "ok" && eintraege.length === 0 && (
        <div className="mt-8 rounded-lg border border-trennlinie bg-seite p-12 text-center">
          <p className="font-display text-xl font-medium">{t("leer")}</p>
          <p className="mx-auto mt-3 max-w-[420px] text-text-sekundaer">
            {t("leerHinweis")}
          </p>
        </div>
      )}

      {lage.art === "ok" && eintraege.length > 0 && (
        <div className="mt-8 overflow-hidden rounded-lg border border-trennlinie bg-seite">
          {eintraege.map((e) => (
            <div key={e.id} className="border-b border-trennlinie last:border-b-0">
              <div className="flex flex-wrap items-center gap-4 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-base font-medium text-text-primaer">
                    {e.title}
                  </p>
                  <p className="mt-1 text-[0.8125rem] text-text-gedaempft">
                    {e.deleted_at
                      ? t("geloeschtAm", {
                          datum: formatMeetingDate(Date.parse(e.deleted_at), locale),
                        })
                      : null}
                    {" · "}
                    {e.endgueltig_am
                      ? t("endgueltigAm", {
                          datum: formatMeetingDate(Date.parse(e.endgueltig_am), locale),
                        })
                      : t("endgueltigBald")}
                  </p>
                  {!e.audio_vorhanden && (
                    // Farbe trägt die Aussage nie allein (DESIGN.md §
                    // Zustände) — deshalb Zeichen und Satz.
                    <p className="mt-2 inline-flex items-center gap-2 text-[0.8125rem] text-text-gedaempft">
                      <span aria-hidden>◦</span>
                      {t("ohneAufnahme")}
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-4">
                  <StatusPill status={e.status} />
                  <p className="mono text-[0.8125rem] font-medium text-text-gedaempft">
                    {formatDuration(e.duration_ms)}
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    onClick={() => zurueckholen(e)}
                    disabled={arbeitet === e.id}
                    className="btn btn-sekundaer inline-flex items-center gap-2"
                  >
                    <RotateCcw size={16} aria-hidden />
                    {t("zurueckholen")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setFragt(fragt === e.id ? null : e.id)}
                    disabled={arbeitet === e.id}
                    aria-expanded={fragt === e.id}
                    className="btn btn-sekundaer inline-flex items-center gap-2"
                  >
                    <Trash2 size={16} aria-hidden />
                    {t("endgueltigLoeschen")}
                  </button>
                </div>
              </div>

              {fragt === e.id && (
                <div className="streifen streifen-achtung mx-5 mb-4">
                  <span className="zeichen" aria-hidden>
                    !
                  </span>
                  <span className="flex-1">
                    <span className="block">
                      {t("endgueltigFrage", { titel: e.title })}
                    </span>
                    <span className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => endgueltig(e)}
                        disabled={arbeitet === e.id}
                        className="btn btn-primaer"
                      >
                        {t("endgueltigBestaetigen")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setFragt(null)}
                        className="btn btn-sekundaer"
                      >
                        {t("abbrechen")}
                      </button>
                    </span>
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
