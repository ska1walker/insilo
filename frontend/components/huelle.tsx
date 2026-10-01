"use client";

/**
 * Die Hülle — Kopfecke, Navigation, Inhalt, Ablage.
 *
 * Baustein AM-HUELLE aus dem AImighty-CI, mit HB-MARKE (Kopfecke) und
 * HB-NAVIGATION; das CSS steht wörtlich in globals.css. Seit Etappe 6 des
 * CI-Anschlusses dasselbe Grundgerüst wie Rocket (CI ABGLEICH, Paket 5):
 *
 * - Kopfecke 240 × 56 mit der AImighty-Wortmarke und „Insilo“ (R4, G1).
 *   Insilo sucht nicht und legt nicht von überall an — die Leiste trägt
 *   deshalb nur die Kopfecke, auf derselben Höhe wie in Rocket.
 * - Navigation 240 px, der gewählte Eintrag mit Goldkante (G1).
 * - Am Handy unten höchstens fünf Ziele: vier und „Mehr“; Einstellungen
 *   und „Über“ stehen unter „Mehr“ (G5).
 * - Am Fuß der Datenschutz-Nachweis, gemessen (IN-B4), und die Herkunft.
 *
 * Die Ablage trägt Kontext zum ausgewählten Ding und ist nie eine zweite
 * Inhaltsspalte. Sie steht nur dort, wo eine Ansicht sie über `useAblage()`
 * befüllt — sonst kollabiert die Spalte.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { DatenschutzNachweis } from "@/components/datenschutz-nachweis";
import { Marke } from "@/components/marke";
import { OffeneAufnahmen } from "@/components/offene-aufnahmen";
import { Archive, Ellipsis, Info, Lightbulb, MessagesSquare, Mic, Settings } from "@/lib/symbole";
import type { SymbolKomponente } from "@/components/symbol";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

// ─── Ablage-Slot ────────────────────────────────────────────────────────
// Eine Ansicht meldet ihren Kontext an, die Hülle rendert ihn. Ohne
// Anmeldung bleibt die Spalte weg.

type AblageContextValue = {
  setAblage: (node: ReactNode) => void;
};

const AblageContext = createContext<AblageContextValue | null>(null);

/**
 * Füllt die Ablage der Hülle. Aufruf in einer Client-Ansicht:
 *   useAblage(<Kontext … />, [abhängigkeiten]);
 * Beim Verlassen der Ansicht wird die Spalte automatisch geleert.
 */
export function useAblage(node: ReactNode) {
  const ctx = useContext(AblageContext);
  useEffect(() => {
    ctx?.setAblage(node);
    return () => ctx?.setAblage(null);
  }, [node]);
}

// ─── Navigation ─────────────────────────────────────────────────────────

type Ziel = {
  href: string;
  schluessel: string;
  icon: SymbolKomponente;
  /** Weitere Pfade, unter denen der Eintrag als gewählt gilt. */
  auch?: string[];
};

/**
 * Fest statt `new Date().getFullYear()`: Server und Browser würden sonst
 * um Mitternacht unterschiedliche Jahre rendern und React meldete einen
 * Hydration-Fehler. Beim Jahreswechsel hier nachziehen.
 */
const JAHR = 2026;

// Die Startseite ist die Aufnahme; eine Besprechung gehört zu „Besprechungen“,
// der Papierkorb auch. Datenschutz und Protokoll stehen unter „Einstellungen“
// — vorher war auf diesen Seiten gar kein Eintrag gewählt.
const HAUPT: Ziel[] = [
  { href: "/aufnahme", schluessel: "record", icon: Mic, auch: ["/"] },
  { href: "/besprechungen", schluessel: "meetings", icon: MessagesSquare, auch: ["/m/", "/papierkorb"] },
  { href: "/archiv", schluessel: "archive", icon: Archive },
  { href: "/idee", schluessel: "idee", icon: Lightbulb },
];

const NACHRANGIG: Ziel[] = [
  { href: "/einstellungen", schluessel: "settings", icon: Settings, auch: ["/datenschutz", "/protokoll"] },
  { href: "/ueber", schluessel: "about", icon: Info },
];

function istAktiv(ziel: Ziel, pfad: string): boolean {
  if (pfad === ziel.href || pfad.startsWith(`${ziel.href}/`)) return true;
  return (ziel.auch ?? []).some((a) => (a === "/" ? pfad === "/" : pfad === a || pfad.startsWith(a)));
}

function NavLink({ ziel, pfad, beschriftung }: { ziel: Ziel; pfad: string; beschriftung: string }) {
  const Icon = ziel.icon;
  const aktiv = istAktiv(ziel, pfad);
  return (
    <Link
      href={ziel.href}
      className={`huelle-nav-item${aktiv ? " aktiv" : ""}`}
      aria-current={aktiv ? "page" : undefined}
      title={beschriftung}
    >
      <Icon size={20} aria-hidden />
      <span>{beschriftung}</span>
    </Link>
  );
}

export function Huelle({ children }: { children: ReactNode }) {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pfad = usePathname();
  const [ablage, setAblage] = useState<ReactNode>(null);
  const [mehr, setMehr] = useState(false);

  // Ein Seitenwechsel schließt „Mehr“.
  useEffect(() => setMehr(false), [pfad]);

  return (
    <AblageContext.Provider value={{ setAblage }}>
      <div className={`huelle${ablage ? " hat-ablage" : ""}`}>
        <header className="kopfleiste">
          <div className="kopfleiste-marke">
            <Link href="/" className="marke" aria-label={t("homeAria")}>
              <Marke />
              <span className="marke-produkt" aria-hidden="true">
                Insilo
              </span>
            </Link>
          </div>
        </header>

        <nav className="huelle-nav" aria-label={t("navAria")}>
          <div className="huelle-nav-gruppe">
            {HAUPT.map((z) => (
              <NavLink key={z.href} ziel={z} pfad={pfad} beschriftung={t(z.schluessel)} />
            ))}
          </div>

          <div className="huelle-nav-spacer" />

          <div className="huelle-nav-gruppe">
            {NACHRANGIG.map((z) => (
              <NavLink key={z.href} ziel={z} pfad={pfad} beschriftung={t(z.schluessel)} />
            ))}
          </div>

          {/* Die schmale Leiste unten: vier Ziele und „Mehr“ (G5). */}
          <div className="huelle-nav-mobil">
            {HAUPT.map((z) => (
              <NavLink key={z.href} ziel={z} pfad={pfad} beschriftung={t(z.schluessel)} />
            ))}
            <button
              type="button"
              className={`huelle-nav-item${mehr || NACHRANGIG.some((z) => istAktiv(z, pfad)) ? " aktiv" : ""}`}
              aria-expanded={mehr}
              aria-controls="huelle-nav-mehr"
              onClick={() => setMehr((o) => !o)}
            >
              <Ellipsis size={20} aria-hidden />
              <span>{t("mehr")}</span>
            </button>
          </div>
          {mehr && (
            <div className="huelle-nav-mehr" id="huelle-nav-mehr" role="group" aria-label={t("mehrAria")}>
              {NACHRANGIG.map((z) => (
                <NavLink key={z.href} ziel={z} pfad={pfad} beschriftung={t(z.schluessel)} />
              ))}
            </div>
          )}

          <div className="huelle-fuss">
            {/* Gemessen oder gar nicht (DESIGN.md §5, CI HB-KONTO). */}
            <DatenschutzNachweis locale={locale} />
            {/* Herkunftsvermerk mit Verweis auf den Hersteller. Die neue
                Seite bekommt weder Zugriff auf dieses Fenster noch die
                Herkunfts-URL mit; von selbst verbindet sich hier nichts. */}
            <p className="huelle-herkunft">
              <a
                href="https://aimighty.de"
                target="_blank"
                rel="noopener noreferrer"
                className="huelle-herkunft-marke"
                aria-label={t("herkunftAria")}
              >
                AImighty
              </a>
              <span className="huelle-herkunft-recht">© {JAHR}</span>
            </p>
          </div>
        </nav>

        <div className="huelle-inhalt">
          {/* Nicht gesendete Aufnahmen stehen über jeder Ansicht, bis sie
              erledigt sind — siehe lib/aufnahmen.ts. */}
          <OffeneAufnahmen />
          {children}
        </div>

        {ablage ? <aside className="huelle-ablage">{ablage}</aside> : null}
      </div>
    </AblageContext.Provider>
  );
}
