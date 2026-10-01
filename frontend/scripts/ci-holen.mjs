// Holt einen Stand des AImighty-CI in die Kopie unter ci/ (ABGLEICH.md,
// Paket 4; Kai, 1.10.2026: Das CI ist die Quelle für alles).
//
//   node scripts/ci-holen.mjs --von ../../aimighty-ci --stand ci-26.10.5
//
// Gelesen wird aus einem Klon des CI-Repos mit `git show <stand>:<pfad>` —
// genau die Dateien des Tags, nicht was im Klon gerade ausgecheckt ist. Das
// Paket (welche Dateien) steht im CI selbst, in werkzeug/stand.py. Geholt
// wird beim Entwickeln, nie beim Bauen; die CI prüft ohne Netz gegen die
// Kopie (tests/ci-stand.test.ts). Danach entsteht lib/symbole.tsx
// neu aus den Zeichen.
//
// Was sich in Insilo ändern soll, ändert sich zuerst im CI (STAND.md dort).
// Übernommen aus Rocket (frontend/scripts/ci-holen.mjs).

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const hier = dirname(fileURLToPath(import.meta.url));
const frontend = join(hier, "..");
const ZIEL = join(frontend, "ci");

function argument(name) {
  const i = process.argv.indexOf(name);
  if (i < 0 || !process.argv[i + 1]) {
    console.error(`Aufruf: node scripts/ci-holen.mjs --von <klon von aimighty-ci> --stand ci-YY.M.n`);
    process.exit(2);
  }
  return process.argv[i + 1];
}

const von = argument("--von");
const stand = argument("--stand");
if (!/^ci-\d+\.\d+\.\d+$/.test(stand)) {
  console.error(`${stand} ist kein Stand (ci-YY.M.n). Apps holen nie main.`);
  process.exit(2);
}

const git = (...a) => execFileSync("git", ["-C", von, ...a], { maxBuffer: 64 * 1024 * 1024 });
const commit = git("rev-parse", `${stand}^{commit}`).toString().trim();

// Das Paket aus werkzeug/stand.py des Stands: die Liste PAKET = [...].
const standPy = git("show", `${stand}:werkzeug/stand.py`).toString();
const muster = [...standPy.match(/PAKET = \[([\s\S]*?)\]/)[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
const alsRegex = (m) => new RegExp(`^${m.replace(/[.]/g, "\\.").replace(/\*/g, "[^/]*")}$`);
const alle = git("ls-tree", "-r", "--name-only", commit).toString().split("\n").filter(Boolean);
const dateien = alle.filter((p) => muster.some((m) => alsRegex(m).test(p))).sort();
for (const m of muster) {
  if (!dateien.some((p) => alsRegex(m).test(p))) throw new Error(`${m} findet im Stand ${stand} nichts`);
}

rmSync(ZIEL, { recursive: true, force: true });
const pruefsummen = {};
for (const pfad of dateien) {
  const inhalt = git("show", `${commit}:${pfad}`);
  mkdirSync(dirname(join(ZIEL, pfad)), { recursive: true });
  writeFileSync(join(ZIEL, pfad), inhalt);
  pruefsummen[pfad] = createHash("sha256").update(inhalt).digest("hex");
}
writeFileSync(
  join(ZIEL, "stand.json"),
  JSON.stringify({ stand, commit, quelle: "ska1walker/aimighty-ci", dateien: pruefsummen }, null, 2) + "\n",
);
console.log(`${stand} (${commit.slice(0, 7)}): ${dateien.length} Dateien nach ci/`);

execFileSync("node", [join(hier, "symbole-erzeugen.mjs")], { stdio: "inherit" });
