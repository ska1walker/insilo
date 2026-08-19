"use client";

/**
 * Die Hülle — Navigation, Inhalt, Ablage.
 *
 * Aus dem AImighty-Designsystem (InSilo_Design-Paket, Abschnitt „Die Hülle"):
 * drei Bereiche, Wappen mit festem Klickziel zur ersten Ansicht, Produktname
 * als Beschriftung (kein Bedienelement — Insilo läuft als einzelnes Produkt),
 * Datenschutz-Nachweis am unteren Rand der Navigation.
 *
 * Die Ablage trägt Kontext zum ausgewählten Ding und ist ausdrücklich nie eine
 * zweite Inhaltsspalte. Sie steht deshalb nur dort, wo eine Ansicht sie über
 * `useAblage()` befüllt — sonst kollabiert die Spalte.
 *
 * Mobil: das Referenzblatt zeigt nur den Zeiger-Fall. Insilo ist aber primär
 * eine Smartphone-PWA, und eine 220px-Spalte hat auf 375px nichts verloren.
 * Unterhalb von 1024px wandert die Navigation deshalb an den unteren Rand
 * (daumennah, PWA-üblich) und die Ablage rutscht unter den Inhalt.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { DatenschutzNachweis } from "@/components/datenschutz-nachweis";
import { Wappen } from "@/components/wappen";
import {
  Archive,
  Info,
  Mic,
  Settings,
  ShowerHead,
  Text,
  type LucideIcon,
} from "lucide-react";
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node]);
}

// ─── Navigation ─────────────────────────────────────────────────────────

type Eintrag = {
  href: string;
  schluessel: string;
  icon: LucideIcon;
  /** Auf der mobilen Leiste ausgeblendet — dort ist Platz für fünf Ziele. */
  nachrangig?: boolean;
};

/**
 * Fest statt `new Date().getFullYear()`: Server und Browser würden sonst
 * um Mitternacht unterschiedliche Jahre rendern und React meldete einen
 * Hydration-Fehler. Beim Jahreswechsel hier nachziehen.
 */
const JAHR = 2026;

const HANDLUNGEN: Eintrag[] = [
  { href: "/aufnahme", schluessel: "record", icon: Mic },
  { href: "/besprechungen", schluessel: "meetings", icon: Text },
  { href: "/archiv", schluessel: "archive", icon: Archive },
  { href: "/idee", schluessel: "idee", icon: ShowerHead },
];

const NACHGEORDNET: Eintrag[] = [
  { href: "/einstellungen", schluessel: "settings", icon: Settings },
  { href: "/ueber", schluessel: "about", icon: Info, nachrangig: true },
];

function NavEintrag({
  eintrag,
  aktiv,
  beschriftung,
}: {
  eintrag: Eintrag;
  aktiv: boolean;
  beschriftung: string;
}) {
  const Icon = eintrag.icon;
  return (
    <Link
      href={eintrag.href}
      className={`huelle-nav-item${aktiv ? " aktiv" : ""}`}
      data-nachrangig={eintrag.nachrangig ? "true" : undefined}
      aria-current={aktiv ? "page" : undefined}
    >
      <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden />
      <span className="huelle-nav-text">{beschriftung}</span>
    </Link>
  );
}

export function Huelle({ children }: { children: ReactNode }) {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();
  const [ablage, setAblage] = useState<ReactNode>(null);

  const istAktiv = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <AblageContext.Provider value={{ setAblage }}>
      <div className={`huelle${ablage ? " hat-ablage" : ""}`}>
        <nav className="huelle-nav" aria-label={t("navAria")}>
          {/* Kopfecke: Wappen klickt zur ersten Ansicht, der Name daneben
              ist Beschriftung — Insilo läuft als einzelnes Produkt. */}
          <div className="huelle-kopfecke">
            <Link href="/" aria-label={t("homeAria")} className="huelle-wappen-link">
              <Wappen className="huelle-wappen" />
            </Link>
          </div>

          <div className="huelle-nav-gruppe">
            {HANDLUNGEN.map((e) => (
              <NavEintrag
                key={e.href}
                eintrag={e}
                aktiv={istAktiv(e.href)}
                beschriftung={t(e.schluessel)}
              />
            ))}
          </div>

          <div className="huelle-nav-spacer" />

          <div className="huelle-nav-gruppe huelle-nav-nachgeordnet">
            {NACHGEORDNET.map((e) => (
              <NavEintrag
                key={e.href}
                eintrag={e}
                aktiv={istAktiv(e.href)}
                beschriftung={t(e.schluessel)}
              />
            ))}
          </div>

          {/* Datenschutz-Nachweis — zeigt sich nur, wenn der Zustand
              abrufbar ist (Paket-Regel: gemessene Werte oder gar nicht). */}
          <DatenschutzNachweis locale={locale} />

          {/* Herkunftsvermerk mit Verweis auf den Hersteller.
              `rel="noopener noreferrer"`: die neue Seite bekommt weder
              Zugriff auf dieses Fenster noch die Herkunfts-URL mit — bei
              einer Box unter eigener Adresse ist das keine Kleinigkeit.
              Der Aufruf geschieht nur auf Klick; von selbst verbindet
              sich hier nichts. */}
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
        </nav>

        {/* Kein <main> hier: die Ansichten bringen ihr eigenes mit.
            Wird beim Seiten-Umzug zusammengeführt. */}
        <div className="huelle-inhalt">{children}</div>

        {ablage ? <aside className="huelle-ablage">{ablage}</aside> : null}
      </div>
    </AblageContext.Provider>
  );
}
