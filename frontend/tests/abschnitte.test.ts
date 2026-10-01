import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Jeder Abschnitt von globals.css trägt eine Kennung (CI STAND.md, „Eine
 * neue App anschließen“, Schritt 3). Nach Rockets `abschnitte.test.ts`.
 *
 * Nur so findet `bauteile.py` die Abschnitte: Jede Kopfzeile
 * `/* ── Titel [KENNUNG] ─…` sagt, wem die Regeln darunter gehören. Ein Kopf
 * ohne Kennung hängte seine Regeln still an den Baustein davor. Innerhalb
 * des Token-Blocks (AM-TOKEN) gliedern Köpfe ohne Kennung nur die Werte.
 *
 * - `AM-`/`HB-` muss es im CI geben (`ci/bauteile/<KENNUNG>.css`);
 * - `IN-` ist Insilos Eigenes und steht in `docs/DESIGN.md` §4a.
 */

const FRONTEND = join(__dirname, "..");
const css = readFileSync(join(FRONTEND, "app", "globals.css"), "utf8");
const design = readFileSync(join(FRONTEND, "..", "docs", "DESIGN.md"), "utf8");

const KOPF = /^\s*\/\* ── /;
const KENNUNG = /\[((?:AM|HB|IN)-[A-Z]+)\]/;

function koepfe() {
  const zeilen = css.split("\n");
  const ende = zeilen.findIndex((z) => z.includes("[AM-BASIS]"));
  return zeilen.map((z, i) => ({ z, nr: i + 1 })).filter(({ z, nr }) => nr > ende && KOPF.test(z));
}

const kennungen = () => new Set(koepfe().map(({ z }) => z.match(KENNUNG)?.[1]).filter(Boolean) as string[]);

describe("Abschnitte in globals.css", () => {
  it("der Token-Block endet mit einem Abschnitt [AM-BASIS]", () => {
    expect(css).toContain("[AM-BASIS]");
  });

  it("jeder Kopf nach dem Token-Block trägt eine Kennung", () => {
    const ohne = koepfe()
      .filter(({ z }) => !KENNUNG.test(z))
      .map(({ nr, z }) => `${nr}: ${z.trim()}`);
    expect(ohne).toEqual([]);
  });

  it("jede AM-/HB-Kennung gibt es im CI", () => {
    const fehlt = [...kennungen()].filter(
      (k) => !k.startsWith("IN-") && !existsSync(join(FRONTEND, "ci", "bauteile", `${k}.css`)),
    );
    expect(fehlt).toEqual([]);
  });

  it("jede IN-Kennung steht in docs/DESIGN.md", () => {
    const fehlt = [...kennungen()].filter((k) => k.startsWith("IN-") && !design.includes(`\`${k}\``));
    expect(fehlt).toEqual([]);
  });
});
