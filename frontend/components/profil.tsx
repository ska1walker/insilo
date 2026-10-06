"use client";

/**
 * Das Profil oben rechts — CI-Baustein HB-KONTO (ABGLEICH G8, Kai 6.10.2026).
 *
 * Ganz rechts in der Kopfleiste, am Desktop und am Handy an derselben
 * Stelle wie in Rocket. Das Menü folgt der festen Reihenfolge des CI:
 * Kopf mit Namen › Einstellungen › Darstellung › Sprache. Ein Abmelden gibt
 * es nicht: Olares meldet an und ab, ein Knopf hier wäre eine Attrappe.
 * Escape, ein Klick außerhalb und ein Seitenwechsel schließen das Menü;
 * der Fokus kehrt zum Knopf zurück.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { liesCookie, setzeCookie, wende, type Darstellung } from "@/components/darstellung";
import { apiGet } from "@/lib/api/client";
import { Check, Globe, Monitor, Moon, Settings, Sun } from "@/lib/symbole";

type Ich = { anmeldename: string; name: string };

/** Zwei Buchstaben aus dem Namen: „Kai Böhm“ → „KB“, „kaivostudio“ → „KA“. */
export function initialen(name: string | null | undefined): string {
  const teile = (name ?? "").trim().split(/[\s._-]+/).filter(Boolean);
  if (teile.length === 0) return "…";
  if (teile.length === 1) return teile[0].slice(0, 2).toUpperCase();
  return (teile[0][0] + teile[teile.length - 1][0]).toUpperCase();
}

export function Profilknopf() {
  const t = useTranslations("konto");
  const pfad = usePathname();
  const [offen, setOffen] = useState(false);
  const [ich, setIch] = useState<Ich | null>(null);
  const knopf = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    apiGet<Ich>("/api/v1/ich").then(setIch).catch(() => setIch(null));
  }, []);

  useEffect(() => setOffen(false), [pfad]);

  const name = ich?.name ?? "…";

  function schliessen(fokus = true) {
    setOffen(false);
    if (fokus) knopf.current?.focus();
  }

  return (
    <div className="person">
      <button
        ref={knopf}
        type="button"
        className="person-knopf"
        aria-expanded={offen}
        aria-haspopup="dialog"
        aria-controls="konto-menue"
        aria-label={t("knopf", { name })}
        title={t("knopf", { name })}
        onClick={() => setOffen((o) => !o)}
      >
        <span className="person-kreis" aria-hidden="true">
          {initialen(ich?.name)}
        </span>
      </button>
      {offen && <Kontomenue ich={ich} schliessen={schliessen} knopf={knopf} />}
    </div>
  );
}

const WAHLEN: { wert: Darstellung; schluessel: string; Zeichen: typeof Sun }[] = [
  { wert: "system", schluessel: "auto", Zeichen: Monitor },
  { wert: "hell", schluessel: "light", Zeichen: Sun },
  { wert: "dunkel", schluessel: "dark", Zeichen: Moon },
];

function Kontomenue({
  ich,
  schliessen,
  knopf,
}: {
  ich: Ich | null;
  schliessen: (fokus?: boolean) => void;
  knopf: React.RefObject<HTMLButtonElement | null>;
}) {
  const t = useTranslations("konto");
  const tD = useTranslations("darstellung");
  const tL = useTranslations("locale.names");
  const locale = useLocale();
  const wurzel = useRef<HTMLDivElement>(null);
  const [wahl, setWahl] = useState<Darstellung | null>(null);

  useEffect(() => {
    setWahl(liesCookie());
    wurzel.current?.querySelector<HTMLElement>("a, button")?.focus();
    function taste(e: KeyboardEvent) {
      if (e.key === "Escape") schliessen(true);
    }
    function klick(e: MouseEvent) {
      const ziel = e.target as Node;
      if (wurzel.current?.contains(ziel) || knopf.current?.contains(ziel)) return;
      schliessen(false);
    }
    document.addEventListener("keydown", taste);
    document.addEventListener("mousedown", klick);
    return () => {
      document.removeEventListener("keydown", taste);
      document.removeEventListener("mousedown", klick);
    };
  }, [schliessen, knopf]);

  function waehle(wert: Darstellung) {
    setWahl(wert);
    setzeCookie(wert);
    wende(wert);
  }

  return (
    <div className="person-liste" id="konto-menue" role="dialog" aria-label={t("menue")} ref={wurzel}>
      <div className="person-kopf">
        <span className="person-kreis" aria-hidden="true">
          {initialen(ich?.name)}
        </span>
        <span className="person-text">
          <span className="person-name">{ich?.name ?? "…"}</span>
          {ich && ich.anmeldename !== ich.name ? <span className="person-unter">{ich.anmeldename}</span> : null}
        </span>
      </div>

      <Link href="/einstellungen" className="person-eintrag">
        <Settings size={16} aria-hidden />
        <span className="person-eintrag-text">{t("einstellungen")}</span>
      </Link>

      <div className="konto-teil" role="group" aria-label={t("darstellung")}>
        <p className="konto-abschnitt">{t("darstellung")}</p>
        {WAHLEN.map(({ wert, schluessel, Zeichen }) => (
          <button
            key={wert}
            type="button"
            className="person-eintrag"
            aria-pressed={wahl === wert}
            onClick={() => waehle(wert)}
          >
            <Zeichen size={16} aria-hidden />
            <span className="person-eintrag-text">{tD(schluessel)}</span>
            {wahl === wert ? <Check size={16} aria-hidden /> : null}
          </button>
        ))}
      </div>

      <div className="konto-teil">
        <p className="konto-abschnitt">{t("sprache")}</p>
        <Link href="/einstellungen#sprache" className="person-eintrag">
          <Globe size={16} aria-hidden />
          <span className="person-eintrag-text">{tL(locale)}</span>
        </Link>
      </div>
    </div>
  );
}
