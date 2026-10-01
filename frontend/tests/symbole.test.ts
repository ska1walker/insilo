import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";
import { strich } from "@/components/symbol";

/**
 * Ein Icon-Set für alle Apps (CI ABGLEICH.md, R2 und IN-Z1/Z2; Kai,
 * 1.10.2026): Insilo zeichnet nur aus dem CI-Set, über HB-SYMBOL. Nach
 * Rockets `symbole.test.ts`. Festgehalten wird:
 * - kein Import aus lucide-react, kein lucide in package.json;
 * - lib/symbole.tsx ist aus der CI-Kopie (ci/marke/icons/ui/) erzeugt;
 * - Größen nur 16/20/24/40 — und die Ausnahme des Aufnahmeknopfs
 *   (Aufnahmezeichen) nur dort, wo der runde Knopf steht;
 * - der Strich bleibt bei jeder Größe 1,5 px.
 */

const FRONTEND = join(__dirname, "..");
const ERLAUBT = new Set(["16", "20", "24", "40"]);
const AUFNAHMEKNOPF = new Set(["components/recording-block.tsx", "components/quick-capture.tsx"]);

function dateien(ordner: string): string[] {
  return readdirSync(ordner).flatMap((name) => {
    if (name === "node_modules" || name.startsWith(".")) return [];
    const pfad = join(ordner, name);
    if (statSync(pfad).isDirectory()) return dateien(pfad);
    return /\.(tsx?|mjs)$/.test(name) ? [pfad] : [];
  });
}

const QUELLEN = ["app", "components", "lib"].flatMap((o) => dateien(join(FRONTEND, o)));
const SYMBOLE = readFileSync(join(FRONTEND, "lib", "symbole.tsx"), "utf8");
const NAMEN = [...SYMBOLE.matchAll(/export const (\w+) = symbol\(/g)].map((m) => m[1]);

describe("HB-SYMBOL", () => {
  it("niemand importiert lucide-react", () => {
    const treffer = QUELLEN.filter((p) => /from\s+["']lucide-react["']/.test(readFileSync(p, "utf8")));
    expect(treffer).toEqual([]);
    expect(readFileSync(join(FRONTEND, "package.json"), "utf8")).not.toContain("lucide");
  });

  it("lib/symbole.tsx ist aus ci/marke/icons/ui/ erzeugt", () => {
    expect(() =>
      execFileSync("node", [join(FRONTEND, "scripts", "symbole-erzeugen.mjs"), "--pruefen"], { stdio: "pipe" }),
    ).not.toThrow();
  });

  it("jedes Zeichen steht in 16, 20, 24 oder 40 px", () => {
    const zeichen = new RegExp(`<(?:${NAMEN.join("|")}|Icon)\\b([^>]*?)/>`, "gs");
    const falsch = QUELLEN.flatMap((p) =>
      [...readFileSync(p, "utf8").matchAll(zeichen)]
        .map((m) => m[1].match(/size=\{(\d+)\}/)?.[1] ?? "16")
        .filter((g) => !ERLAUBT.has(g))
        .map((g) => `${relative(FRONTEND, p)}: ${g} px`),
    );
    expect(falsch).toEqual([]);
  });

  it("kein Zeichen setzt seinen Strich selbst", () => {
    const zeichen = new RegExp(`<(?:${NAMEN.join("|")}|Icon)\\b[^>]*strokeWidth`, "s");
    expect(QUELLEN.filter((p) => zeichen.test(readFileSync(p, "utf8"))).map((p) => relative(FRONTEND, p))).toEqual([]);
  });

  it("die Größe des Aufnahmeknopfs nur am Aufnahmeknopf", () => {
    const nutzer = QUELLEN.filter((p) => /<Aufnahmezeichen\b/.test(readFileSync(p, "utf8"))).map((p) =>
      relative(FRONTEND, p),
    );
    expect(nutzer.filter((p) => !AUFNAHMEKNOPF.has(p))).toEqual([]);
  });

  it("Strich 1,5 px bei jeder Größe", () => {
    for (const groesse of [16, 20, 24, 40, 36, 80, 96]) {
      expect((strich(groesse) * groesse) / 24).toBeCloseTo(1.5);
    }
  });
});
