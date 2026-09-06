import type { Config } from "tailwindcss";
// Preset kommt als JS aus dem Design-Paket und wird bewusst unverändert
// gelassen — Änderungen gehören in die Quelle, nicht in unsere Kopie.
// Der Cast ist nötig, weil TS `darkMode: ["class", "dunkel"]` als string[]
// inferiert statt als Tupel.
import insiloPreset from "./tailwind.insilo.preset";

const insilo = insiloPreset as unknown as Config;

const config: Config = {
  // AImighty-Designsystem. Das Preset dupliziert keine Werte, es liest die
  // CSS-Variablen aus app/globals.css. Bauteile nutzen die deutschen
  // Klassen (bg-flaeche-1, text-primaer, …).
  //
  // Die englische Alt-Palette (Weiß/Schwarz/Gold, Lexend Deca, Inter,
  // JetBrains Mono, 8-px-Raster) ist am 06.09.2026 entfernt worden. Sie
  // stand seit dem 18.08. ungenutzt daneben — mit einer Ausnahme, die
  // jeder gesehen hat: `font-display` und `font-mono` zeigten auf
  // Schriften, die nie geladen wurden, und jede Überschrift rendert in der
  // Fallback-Schrift des Browsers. Beide Klassen zeigen jetzt auf Geist.
  presets: [insilo],
  content: [
    "./src/**/*.{ts,tsx,mdx}",
    "./app/**/*.{ts,tsx,mdx}",
    "./components/**/*.{ts,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Eine Familie für Überschrift und Fließtext — Geist Sans. `display`
        // bleibt als Name stehen, damit 29 Stellen nicht umgeschrieben
        // werden; es ist dieselbe Schrift.
        sans: ["var(--am-schrift-sans)"],
        display: ["var(--am-schrift-sans)"],
        mono: ["var(--am-schrift-mono)"],
      },
    },
  },
  plugins: [],
};

export default config;
