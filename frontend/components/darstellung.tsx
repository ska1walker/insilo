"use client";

/**
 * Hell / Dunkel / Wie das System.
 *
 * Der Dunkelmodus des AImighty-Systems ist kein Farbfilter, sondern eine
 * eigene Rollenverteilung: im Hellmodus handelt Hanseatenblau und Gold
 * zeichnet aus, im Dunkelmodus handelt Gold — „Blau auf Blau trägt nicht"
 * (dokumentierte Ausnahme im Paket). Beides steckt in den Token, hier wird
 * nur die Klasse `dunkel` am <html> gesetzt.
 *
 * Bewusst nur ein Cookie, keine Server-Persistenz wie bei der Sprache:
 * die Wahl ist gerätebezogen sinnvoll (am Schreibtisch hell, abends am
 * Telefon dunkel) und hat im Benutzerkonto nichts verloren.
 */

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

export const DARSTELLUNG_COOKIE = "insilo-darstellung";

export type Darstellung = "hell" | "dunkel" | "system";

/**
 * Läuft als Inline-Script vor dem ersten Anstrich (siehe layout.tsx).
 * Ohne das blitzt bei dunkler Einstellung kurz die helle Fläche auf.
 * Bewusst als String und ohne Abhängigkeiten — er läuft, bevor React da ist.
 */
export const DARSTELLUNG_SCRIPT = `
(function () {
  try {
    var m = document.cookie.match(/(?:^|;\\s*)insilo-darstellung=([^;]*)/);
    var wahl = m ? m[1] : "system";
    var dunkel =
      wahl === "dunkel" ||
      (wahl !== "hell" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    if (dunkel) document.documentElement.classList.add("dunkel");
  } catch (e) {}
})();
`;

function setzeCookie(wert: Darstellung) {
  const ablauf = new Date();
  ablauf.setTime(ablauf.getTime() + 365 * 86400 * 1000);
  document.cookie = `${DARSTELLUNG_COOKIE}=${wert}; Path=/; Expires=${ablauf.toUTCString()}; SameSite=Lax`;
}

function liesCookie(): Darstellung {
  if (typeof document === "undefined") return "system";
  const m = document.cookie.match(/(?:^|;\s*)insilo-darstellung=([^;]*)/);
  const wert = m?.[1];
  return wert === "hell" || wert === "dunkel" ? wert : "system";
}

function wende(wahl: Darstellung) {
  const dunkel =
    wahl === "dunkel" ||
    (wahl === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dunkel", dunkel);
}

const WAHLEN: { wert: Darstellung; schluessel: string; icon: typeof Sun }[] = [
  { wert: "system", schluessel: "auto", icon: Monitor },
  { wert: "hell", schluessel: "light", icon: Sun },
  { wert: "dunkel", schluessel: "dark", icon: Moon },
];

export function DarstellungSwitcher() {
  const t = useTranslations("darstellung");
  // Vor der Hydration nichts markieren — der Server kennt den Cookie nicht
  // und würde sonst eine andere Auswahl rendern als der Browser.
  const [wahl, setWahl] = useState<Darstellung | null>(null);

  useEffect(() => {
    setWahl(liesCookie());
  }, []);

  // Bei „Wie das System" auf Änderungen der Systemeinstellung hören.
  useEffect(() => {
    if (wahl !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const beiWechsel = () => wende("system");
    mq.addEventListener("change", beiWechsel);
    return () => mq.removeEventListener("change", beiWechsel);
  }, [wahl]);

  function waehle(wert: Darstellung) {
    setWahl(wert);
    setzeCookie(wert);
    wende(wert);
  }

  return (
    <div className="space-y-4 rounded-lg border border-trennlinie bg-seite p-6">
      <header>
        <h3 className="text-sm font-medium text-text-primaer">{t("title")}</h3>
        <p className="mt-1 text-xs text-text-sekundaer">{t("hint")}</p>
      </header>

      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {WAHLEN.map(({ wert, schluessel, icon: Icon }) => {
          const aktiv = wahl === wert;
          return (
            <button
              key={wert}
              type="button"
              onClick={() => waehle(wert)}
              aria-pressed={aktiv}
              className={`flex items-center justify-between rounded-mittel border px-4 py-3 text-left text-sm transition-colors ${
                aktiv
                  ? "border-gold-600 bg-gold-200 text-text-primaer"
                  : "border-trennlinie text-text-sekundaer hover:bg-flaeche-1"
              }`}
              style={{ minHeight: "var(--am-ziel-zeiger)" }}
            >
              <span className="flex items-center gap-3">
                <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden />
                {t(schluessel)}
              </span>
              {aktiv ? (
                <Check
                  className="h-3.5 w-3.5"
                  strokeWidth={2}
                  style={{ color: "var(--am-gold-beschriftung)" }}
                  aria-hidden
                />
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
