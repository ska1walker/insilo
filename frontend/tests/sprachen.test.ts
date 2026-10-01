import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Jede der fünf Sprachen kennt dieselben Schlüssel mit denselben Platzhaltern.
 *
 * Fehlt ein Schlüssel, zeigt next-intl seinen Namen statt eines Satzes; fehlt
 * ein `{name}`, steht eine Lücke. Seit Etappe 2 des CI-Anschlusses kommen auch
 * die Texte von Archiv, Besprechungen, Einstellungen und Besprechungsseite aus
 * `messages/` statt fest aus dem Code.
 */

const SPRACHEN = ["de", "en", "fr", "es", "it"];

function flach(wert: unknown, pfad = ""): Record<string, string> {
  if (typeof wert === "string") return { [pfad]: wert };
  return Object.entries(wert as Record<string, unknown>).reduce(
    (alle, [k, v]) => ({ ...alle, ...flach(v, pfad ? `${pfad}.${k}` : k) }),
    {} as Record<string, string>,
  );
}

const TEXTE = Object.fromEntries(
  SPRACHEN.map((s) => [s, flach(JSON.parse(readFileSync(join(__dirname, "..", "messages", `${s}.json`), "utf8")))]),
);

// Einfache Platzhalter `{name}` und Marken `<code>`; Plural-Blöcke von ICU
// tragen übersetzte Wörter und werden nur am Namen verglichen.
function marken(text: string): string[] {
  const namen = [...text.matchAll(/\{(\w+)(?=[,}])/g)].map((m) => `{${m[1]}}`);
  const tags = [...text.matchAll(/<(\w+)>/g)].map((m) => `<${m[1]}>`);
  return [...new Set([...namen, ...tags])].sort();
}

describe("Sprachen", () => {
  it.each(SPRACHEN.slice(1))("%s hat dieselben Schlüssel wie de", (s) => {
    expect(Object.keys(TEXTE[s]).sort()).toEqual(Object.keys(TEXTE.de).sort());
  });

  it.each(SPRACHEN.slice(1))("%s hat dieselben Platzhalter wie de", (s) => {
    const abweichend = Object.keys(TEXTE.de).filter(
      (k) => k in TEXTE[s] && marken(TEXTE[s][k]).join() !== marken(TEXTE.de[k]).join(),
    );
    expect(abweichend).toEqual([]);
  });
});
