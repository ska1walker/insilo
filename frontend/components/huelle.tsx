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
 * - Am Handy unten die vier Ziele (G5).
 * - Einstellungen und „Über Insilo“ nur im Profil oben rechts — nicht in
 *   der Navigation, nicht am Handy (G8 Nachtrag, Kai 6.10.2026).
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
import { Archive, Lightbulb, MessagesSquare, Mic } from "@/lib/symbole";
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
// der Papierkorb auch.
const HAUPT: Ziel[] = [
  { href: "/aufnahme", schluessel: "record", icon: Mic, auch: ["/"] },
  { href: "/besprechungen", schluessel: "meetings", icon: MessagesSquare, auch: ["/m/", "/papierkorb"] },
  { href: "/archiv", schluessel: "archive", icon: Archive },
  { href: "/idee", schluessel: "idee", icon: Lightbulb },
];

// Einstellungen und „Über Insilo“ stehen nicht in der Navigation, sondern im
// Profil oben rechts (CI HB-KONTO, G8 Nachtrag, Kai 6.10.2026).

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

          {/* Die schmale Leiste unten: die vier Ziele. Ein „Mehr“ gibt es nicht
              mehr — Einstellungen und „Über“ stehen im Profil oben rechts. */}
          <div className="huelle-nav-mobil">
            {HAUPT.map((z) => (
              <NavLink key={z.href} ziel={z} pfad={pfad} beschriftung={t(z.schluessel)} />
            ))}
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
