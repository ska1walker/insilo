"use client";

/**
 * Nicht gesendete Aufnahmen — als Karte an der Stelle, wo das Senden
 * scheiterte, und als Liste über jeder Ansicht, sobald eine verwaist ist
 * (Tab geschlossen, abgestürzt, neu geladen).
 *
 * Hintergrund: `lib/aufnahmen.ts`. Die Regel dahinter ist schlicht: eine
 * Aufnahme verschwindet nie still. Sie wird gesendet, als Datei
 * gespeichert oder ausdrücklich verworfen — und Verwerfen fragt nach.
 */

import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import { ApiError } from "@/lib/api/client";
import type { MeetingDto } from "@/lib/api/meetings";
import {
  alsDateiSpeichern,
  beiAenderung,
  dauerVon,
  offeneAufnahmen,
  sendenMitSperre,
  verwerfen,
  type AufnahmeKopf,
} from "@/lib/aufnahmen";
import { formatDuration } from "@/lib/format";

export function useSendefehler() {
  const t = useTranslations("aufnahmeSicherung");
  return useCallback(
    (fehler: unknown) =>
      fehler instanceof ApiError
        ? t("fehlerHttp", { status: fehler.status })
        : t("fehlerNetz"),
    [t],
  );
}

export function OffeneAufnahme({
  kopf,
  ton,
  gesichert = true,
  fehler: fehlerAnfangs = null,
  senden,
  nachSenden,
  nachVerwerfen,
}: {
  kopf: AufnahmeKopf;
  /** Inhalt aus dem Arbeitsspeicher, falls vorhanden. */
  ton?: Blob;
  gesichert?: boolean;
  fehler?: string | null;
  senden: () => Promise<MeetingDto | null>;
  nachSenden: (besprechung: MeetingDto) => void;
  nachVerwerfen: () => void;
}) {
  const t = useTranslations("aufnahmeSicherung");
  const locale = useLocale();
  const sendefehler = useSendefehler();
  const [fehler, setFehler] = useState<string | null>(fehlerAnfangs);
  const [sendet, setSendet] = useState(false);
  const [fragt, setFragt] = useState(false);

  useEffect(() => setFehler(fehlerAnfangs), [fehlerAnfangs]);

  const mb = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format((ton?.size ?? kopf.bytes) / 1024 / 1024);

  async function erneutSenden() {
    setSendet(true);
    setFehler(null);
    try {
      const besprechung = await senden();
      if (besprechung) nachSenden(besprechung);
      else setFehler(t("andererTab"));
    } catch (e) {
      console.error("upload retry failed", e);
      setFehler(sendefehler(e));
    } finally {
      setSendet(false);
    }
  }

  async function speichern() {
    try {
      await alsDateiSpeichern(kopf, ton);
    } catch (e) {
      console.error("saving recording as file failed", e);
      setFehler(t("speichernFehler"));
    }
  }

  async function endgueltigVerwerfen() {
    try {
      await verwerfen(kopf.id);
    } catch {
      /* nichts gesichert — dann gibt es auch nichts zu löschen */
    }
    nachVerwerfen();
  }

  return (
    <div className="streifen streifen-achtung text-left" role="alert">
      <span className="zeichen" aria-hidden>
        !
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{t("titel")}</p>
        <p className="mono mt-1 text-xs text-text-gedaempft">
          {kopf.titel} · {formatDuration(dauerVon(kopf))} · {mb} MB
        </p>
        <p className="mt-2 text-sm text-text-sekundaer">
          {gesichert ? t("gesichert") : t("nichtGesichert")}
        </p>
        {fehler && <p className="mt-2 text-sm text-fehler">{fehler}</p>}

        {fragt ? (
          <div className="mt-4">
            <p className="text-sm">{t("verwerfenFrage")}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="btn btn-sekundaer"
                onClick={endgueltigVerwerfen}
              >
                {t("verwerfenJa")}
              </button>
              <button
                type="button"
                className="btn btn-still"
                onClick={() => setFragt(false)}
              >
                {t("behalten")}
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-primaer"
              onClick={erneutSenden}
              disabled={sendet}
            >
              {sendet && (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              )}
              {sendet ? t("sendet") : t("erneutSenden")}
            </button>
            <button
              type="button"
              className="btn btn-sekundaer"
              onClick={speichern}
              disabled={sendet}
            >
              {t("alsDatei")}
            </button>
            <button
              type="button"
              className="btn btn-still"
              onClick={() => setFragt(true)}
              disabled={sendet}
            >
              {t("verwerfen")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** Die Liste über jeder Ansicht. Leer, solange nichts offen ist. */
export function OffeneAufnahmen() {
  const t = useTranslations("aufnahmeSicherung");
  const router = useRouter();
  const pathname = usePathname();
  const toast = useToast();
  const [offen, setOffen] = useState<AufnahmeKopf[]>([]);

  const laden = useCallback(() => {
    offeneAufnahmen().then(setOffen, () => setOffen([]));
  }, []);

  useEffect(() => {
    laden();
    const abmelden = beiAenderung(laden);
    const sichtbar = () => {
      if (document.visibilityState === "visible") laden();
    };
    document.addEventListener("visibilitychange", sichtbar);
    return () => {
      abmelden();
      document.removeEventListener("visibilitychange", sichtbar);
    };
  }, [laden, pathname]);

  if (offen.length === 0) return null;

  return (
    <div className="mx-auto flex max-w-[720px] flex-col gap-3 px-6 pt-6 md:px-12">
      {offen.map((kopf) => (
        <OffeneAufnahme
          key={kopf.id}
          kopf={kopf}
          senden={() => sendenMitSperre(kopf)}
          nachSenden={(besprechung) => {
            laden();
            if (kopf.quickMode) {
              toast.show({ message: t("gesendet"), variant: "success" });
            } else {
              router.push(`/m/${besprechung.id}`);
            }
          }}
          nachVerwerfen={laden}
        />
      ))}
    </div>
  );
}
