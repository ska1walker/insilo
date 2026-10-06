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
 *   die Kopfecke und ganz rechts das Profil (HB-KONTO, G8), auf
 *   derselben Höhe und an derselben Stelle wie in Rocket.
 * - Navigation 240 px, der gewählte Eintrag mit Goldkante (G1).
 * - Am Handy unten höchstens fünf Ziele: vier und „Mehr“; Einstellungen
 *   und „Über“ stehen unter „Mehr“ (G5).
 * - Kein Fuß in der Navigation (G8, Kai 6.10.2026): Datenschutz-Nachweis
 *   und Herkunft stehen auf „Über Insilo“.
 *
 * Die Ablage trägt Kontext zum ausgewählten Ding und ist nie eine zweite
 * Inhaltsspalte. Sie steht nur dort, wo eine Ansicht sie über `useAblage()`
 * befüllt — sonst kollabiert die Spalte.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Marke } from "@/components/marke";
import { OffeneAufnahmen } from "@/components/offene-aufnahmen";
import { Profilknopf } from "@/components/profil";
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
          {/* Ganz rechts, auf jedem Gerät an derselben Stelle (CI HB-KONTO). */}
          <Profilknopf />
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
