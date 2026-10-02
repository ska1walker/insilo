import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Kontrast aus den Token gerechnet, hell und dunkel.
 *
 * axe im Rundgang misst Schrift gegen ihren Grund — aber nur, was gerade
 * zu sehen ist, und nie Ränder oder Fokusringe (WCAG 1.4.11). So standen
 * in Rocket bis 26.10.4 der Rand des sekundären Knopfs bei 1,86:1, der Fokusring im
 * Dunkeln bei 2,62:1 und die Schrift auf dem Lösch-Knopf im Dunkeln bei
 * 2,45:1, ohne dass ein Test rot wurde (ABGLEICH.md im CI, T9). Dieser
 * Test rechnet jedes Paar, das die Oberfläche bilden kann.
 */

const CSS = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

function block(selektor: string): Record<string, string> {
  const start = CSS.search(new RegExp(`(^|\\n)${selektor.replace(".", "\\.")} \\{`));
  if (start < 0) throw new Error(`Block ${selektor} fehlt`);
  const rumpf = CSS.slice(start, CSS.indexOf("\n}", start));
  const werte: Record<string, string> = {};
  for (const m of rumpf.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/(--am-[\w-]+)\s*:\s*([^;]+);/g)) {
    werte[m[1]] = m[2].trim().toLowerCase();
  }
  return werte;
}

const HELL = block(":root");
const DUNKEL = { ...HELL, ...block("html.dunkel") };

function farbe(token: string, satz: Record<string, string>): string {
  let wert = satz[token];
  for (let i = 0; i < 8 && wert?.startsWith("var("); i++) wert = satz[wert.slice(4, -1).trim()];
  if (!wert || !/^#[0-9a-f]{6}$/.test(wert)) throw new Error(`${token} ist keine Farbe: ${wert}`);
  return wert;
}

function leuchtdichte(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function kontrast(a: string, b: string): number {
  const [x, y] = [leuchtdichte(a), leuchtdichte(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

const FLAECHEN = ["--am-seite", "--am-flaeche-1", "--am-flaeche-2", "--am-flaeche-3"];

// [Vordergrund, Gründe, Mindestwert, wofür]
const PAARE: [string, string[], number, string][] = [
  ["--am-text-primaer", FLAECHEN, 4.5, "Text"],
  ["--am-text-sekundaer", FLAECHEN, 4.5, "Etikett"],
  ["--am-text-gedaempft", FLAECHEN, 4.5, "Nebentext, auch in der Zeile unter dem Zeiger"],
  ["--am-gold-beschriftung", ["--am-seite", "--am-flaeche-1"], 4.5, "Gold als Schrift"],
  ["--am-erfolg", ["--am-seite"], 4.5, "Zustand als Schrift"],
  ["--am-hinweis", ["--am-seite"], 4.5, "Zustand als Schrift"],
  ["--am-achtung", ["--am-seite"], 4.5, "Zustand als Schrift"],
  ["--am-fehler", ["--am-seite", "--am-flaeche-1"], 4.5, "Zustand als Schrift, auch in Karten (Briefing, Board)"],
  // HB-PILLE in der Zustandsfassung (IN-B5): Schrift auf der eigenen Fläche.
  ["--am-erfolg", ["--am-erfolg-flaeche"], 4.5, "Zustandspille „fertig“"],
  ["--am-fehler", ["--am-fehler-flaeche"], 4.5, "Zustandspille „Fehler“"],
  ["--am-handlung-text", ["--am-handlung-ruhend", "--am-handlung-hover", "--am-fehler"], 4.5, "Schrift auf Knopf"],
  ["--am-rand-betont-farbe", ["--am-seite", "--am-flaeche-1", "--am-flaeche-3"], 3, "Rand eines Bedienelements"],
  ["--am-fokus-ring", ["--am-seite", "--am-flaeche-1", "--am-flaeche-3"], 3, "Fokusring"],
  ["--am-handlung-ruhend", ["--am-seite", "--am-flaeche-1"], 3, "Knopffläche"],
  // Insilo: die gewählte Zeile (Besprechung, Vorlage, Sprecher) und die
  // Pille der laufenden Aufnahme liegen auf der Auswahlfläche (ABGLEICH IN-T2).
  ["--am-text-primaer", ["--am-auswahl-flaeche"], 4.5, "Text auf gewählter Zeile"],
  ["--am-text-sekundaer", ["--am-auswahl-flaeche"], 4.5, "Beschreibung der gewählten Vorlage"],
  // Gold als Schrift auf der goldenen Fläche kam auf 3,65:1 (Pille „fasst
  // zusammen“, gewählter Sprecher). Dort steht jetzt Textfarbe; das Gold
  // tragen Punkt und Rand. Gold als Schrift nur auf Seite und Fläche 1.
];

describe.each([
  ["hell", HELL],
  ["dunkel", DUNKEL],
] as const)("Kontrast %s", (_modus, satz) => {
  it("erreicht jedes Paar seinen Mindestwert", () => {
    const zuWenig = PAARE.flatMap(([vorn, gruende, soll, wofuer]) =>
      gruende
        .map((grund) => [grund, kontrast(farbe(vorn, satz), farbe(grund, satz))] as const)
        .filter(([, k]) => k < soll)
        .map(([grund, k]) => `${vorn} auf ${grund}: ${k.toFixed(2)}:1, nötig ${soll}:1 (${wofuer})`),
    );
    expect(zuWenig).toEqual([]);
  });
});

describe("Kontrastrechnung", () => {
  it("rechnet wie WCAG", () => {
    expect(kontrast("#ffffff", "#000000")).toBeCloseTo(21, 5);
    expect(kontrast("#002f56", "#ffffff")).toBeCloseTo(13.63, 2);
  });
});
