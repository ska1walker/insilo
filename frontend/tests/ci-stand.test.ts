import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Insilo hält den Stand des AImighty-CI, ohne Netz geprüft.
 *
 * Das CI ist die Quelle für Token, Zeichen und Bausteine (ABGLEICH.md,
 * Paket 4; Kai, 1.10.2026). `scripts/ci-holen.mjs` holt einen Stand
 * `ci-YY.M.n` nach `ci/`; dieser Test prüft, dass die Kopie unverändert ist
 * und Insilo ihr entspricht. Weicht etwas ab, wird es zuerst im CI geändert
 * und neu geholt — nie hier still angepasst.
 */

const FRONTEND = join(__dirname, "..");
const CI = join(FRONTEND, "ci");
const stand = JSON.parse(readFileSync(join(CI, "stand.json"), "utf8")) as {
  stand: string;
  commit: string;
  dateien: Record<string, string>;
};

function dateien(ordner: string): string[] {
  return readdirSync(ordner).flatMap((name) => {
    const pfad = join(ordner, name);
    return statSync(pfad).isDirectory() ? dateien(pfad) : [relative(CI, pfad)];
  });
}

describe(`CI-Stand ${stand.stand}`, () => {
  it("ist ein Stand, nicht main", () => {
    expect(stand.stand).toMatch(/^ci-\d+\.\d+\.\d+$/);
    expect(stand.commit).toMatch(/^[0-9a-f]{40}$/);
  });

  it("die Kopie ist unverändert: jede Datei passt zu ihrer Prüfsumme", () => {
    const da = dateien(CI).filter((p) => p !== "stand.json").sort();
    expect(da).toEqual(Object.keys(stand.dateien).sort());
    const abweichend = da.filter(
      (p) => createHash("sha256").update(readFileSync(join(CI, p))).digest("hex") !== stand.dateien[p],
    );
    expect(abweichend).toEqual([]);
  });

  it("der Token-Block in globals.css ist tokens/app.css", () => {
    const ab = (text: string) => text.slice(text.indexOf(":root {"));
    const css = readFileSync(join(FRONTEND, "app", "globals.css"), "utf8");
    const ende = css.indexOf('html[data-dichte="kompakt"]');
    const block = ab(css.slice(0, css.indexOf("\n", ende) + 1));
    expect(block).toBe(ab(readFileSync(join(CI, "tokens", "app.css"), "utf8")));
  });

  it("jeder Baustein-Abschnitt ist gleich bauteile/<KENNUNG>.css", () => {
    let meldung = "";
    try {
      meldung = execFileSync(
        "python3",
        [join(CI, "werkzeug", "bauteile.py"), join(FRONTEND, "app", "globals.css"), "--ohne-md"],
        { encoding: "utf8", stdio: "pipe" },
      );
    } catch (e) {
      meldung = (e as { stdout?: string }).stdout ?? String(e);
    }
    // Insilo trägt nicht jeden Baustein des CI (kein Board, keine Kennzahl,
    // kein Assistent). Ein fehlender Abschnitt ist deshalb kein Befund;
    // jeder vorhandene muss gleich sein, und jede Kopfzeile braucht eine
    // Kennung. Anders als Rocket, das jeden Baustein führt.
    const befunde = meldung
      .trim()
      .split("\n")
      .filter((z) => z && !/die App hat keinen Abschnitt/.test(z) && !/^\d+ Befund\(e\)$/.test(z) && !/gleich mit dem CI$/.test(z));
    expect(befunde).toEqual([]);
  });

  it("die Bausteine, die Insilo trägt", () => {
    const css = readFileSync(join(FRONTEND, "app", "globals.css"), "utf8");
    const kennungen = [...new Set([...css.matchAll(/\/\* ── [^\n]*\[((?:AM|HB)-[A-Z]+)\]/g)].map((m) => m[1]))];
    // Wer einen Baustein weglässt, den Insilo schon hatte, merkt es hier.
    expect(kennungen.sort()).toEqual(
      ["AM-BASIS", "AM-FELD", "AM-HAKEN", "AM-HUELLE", "AM-KARTE", "AM-KNOPF", "AM-LEER", "HB-DIALOG", "HB-KONTO", "HB-MARKE", "HB-PILLE", "HB-SYMBOL", "HB-TABELLE", "HB-ZUSTAND"].sort(),
    );
  });
});
