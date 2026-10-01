import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * „AI“, nicht „KI“ und nicht „IA“ — in allem, was ein Mensch in Insilo
 * liest, in jeder der fünf Sprachen.
 *
 * Entschieden von Kai am 1.10.2026 im Abgleich mit dem AImighty-CI
 * (ABGLEICH.md, R3 und IN-R3; `kern/wording.md`): Das Kürzel heißt überall
 * AI, auch im Französischen, Spanischen und Italienischen. Wo das Gemeinte
 * genauer ist, steht das Gemeinte („das Sprachmodell“). Nach Rockets
 * `wording.test.ts`, dazu die Übersetzungen in `messages/`. Bezeichner wie
 * `hintAi` sind keine Wörter — gesucht wird das großgeschriebene Wort.
 */

const FRONTEND = join(__dirname, "..");
const BACKEND = join(FRONTEND, "..", "backend", "app");
const WORT = /\b(KI|IA)\b/;

function dateien(ordner: string, endung: RegExp): string[] {
  return readdirSync(ordner).flatMap((name) => {
    if (name === "node_modules" || name.startsWith(".") || name === "__pycache__") return [];
    const pfad = join(ordner, name);
    if (statSync(pfad).isDirectory()) return dateien(pfad, endung);
    return endung.test(name) ? [pfad] : [];
  });
}

function ohneKommentareTs(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

function ohneKommentarePy(text: string): string {
  return text.replace(/"""[\s\S]*?"""/g, "").replace(/#.*$/gm, "");
}

function fundstellen(pfade: string[], saeubern: (t: string) => string): string[] {
  return pfade.flatMap((pfad) =>
    saeubern(readFileSync(pfad, "utf8"))
      .split("\n")
      .filter((zeile) => WORT.test(zeile))
      .map((zeile) => `${pfad.replace(FRONTEND, "frontend")}: ${zeile.trim()}`),
  );
}

function texte(wert: unknown, pfad = ""): [string, string][] {
  if (typeof wert === "string") return [[pfad, wert]];
  if (wert && typeof wert === "object") {
    return Object.entries(wert).flatMap(([k, v]) => texte(v, pfad ? `${pfad}.${k}` : k));
  }
  return [];
}

describe("Wording", () => {
  it.each(["de", "en", "fr", "es", "it"])("messages/%s.json sagt AI, nicht KI oder IA", (sprache) => {
    const daten = JSON.parse(readFileSync(join(FRONTEND, "messages", `${sprache}.json`), "utf8"));
    const treffer = texte(daten)
      .filter(([, text]) => WORT.test(text))
      .map(([schluessel, text]) => `${schluessel}: ${text}`);
    expect(treffer).toEqual([]);
  });

  it("die Oberfläche sagt AI, nicht KI oder IA", () => {
    const pfade = ["app", "components", "lib"].flatMap((o) => dateien(join(FRONTEND, o), /\.tsx?$/));
    expect(fundstellen(pfade, ohneKommentareTs)).toEqual([]);
  });

  it("die Meldungen des Backends sagen AI, nicht KI oder IA", () => {
    expect(fundstellen(dateien(BACKEND, /\.py$/), ohneKommentarePy)).toEqual([]);
  });
});
