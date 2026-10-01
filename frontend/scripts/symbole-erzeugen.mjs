// HB-SYMBOL — erzeugt lib/symbole.tsx aus den Zeichen des CI-Stands.
//
// Die Zeichen liegen in der Kopie des CI-Stands, ci/marke/icons/ui/ (geholt
// mit scripts/ci-holen.mjs, ABGLEICH.md Paket 4). Ein Zeichen kommt zuerst
// ins CI-Set, über dessen Erzeuger, dann mit einem neuen Stand hierher
// (ABGLEICH.md, R2; Kai, 1.10.2026). Insilo zeichnet nichts direkt aus Lucide.
//
//   node scripts/symbole-erzeugen.mjs                 # schreibt lib/symbole.tsx
//   node scripts/symbole-erzeugen.mjs --pruefen       # Rückgabe 1, wenn etwas abweicht
//
// Die Exportnamen sind die lucide-react-Namen des Zeichens, das das CI-Set
// zeigt — wo Insilo ein vorhandenes Zeichen des Sets nimmt (ABGLEICH IN-Z1),
// heißt der Export nach diesem (Text → MessagesSquare, ShowerHead →
// Lightbulb …), damit der Name sagt, was man sieht. Nach Rocket
// (frontend/scripts/symbole-erzeugen.mjs).

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const hier = dirname(fileURLToPath(import.meta.url));
const frontend = join(hier, "..");
const ZEICHEN = join(frontend, "ci", "marke", "icons", "ui");

export const NAMEN = {
  AlertCircle: "fehler",
  AlertTriangle: "achtung",
  Archive: "datensicherung",
  ArchiveRestore: "wiederherstellen",
  ArrowDown: "pfeil-runter",
  ArrowLeft: "zurueck",
  ArrowRight: "weiter",
  Brain: "gedaechtnis",
  Building2: "firma",
  Check: "erfolg",
  CheckCircle2: "erledigt",
  ChevronDown: "chevron",
  ChevronRight: "chevron-rechts",
  ChevronUp: "chevron-hoch",
  Copy: "kopieren",
  Database: "datenbank",
  Ellipsis: "mehr",
  FileText: "dokumente",
  Folder: "ordner",
  Globe: "netzrecherche",
  Info: "hinweis",
  KeyRound: "schluessel",
  Lightbulb: "erkenntnis",
  Loader2: "laden",
  Lock: "schloss",
  Lokal: "lokal",
  MessagesSquare: "besprechung",
  Mic: "mikrofon",
  Monitor: "geraet-bildschirm",
  Moon: "modus",
  Pencil: "bearbeiten",
  Plus: "plus",
  Quote: "quellenangabe",
  RefreshCw: "neu-laden",
  ScrollText: "protokoll",
  Search: "suche",
  Send: "senden",
  Server: "node",
  Settings: "einstellungen",
  Share2: "weitergabe",
  ShieldCheck: "geschuetzt",
  Sparkles: "ai",
  Square: "stopp",
  Star: "standard",
  Sun: "hell",
  Tag: "schlagwort",
  Trash2: "loeschen",
  Upload: "hochladen",
  User: "nutzer",
  Waves: "welle",
  X: "schliessen",
};

const KOPF =
  '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" ' +
  'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" ' +
  'stroke-linejoin="round">';

/** Die Kinder eines CI-Zeichens als JSX. Der Rumpf muss genau der des Sets sein. */
export function inhalt(name) {
  const text = readFileSync(join(ZEICHEN, `${name}.svg`), "utf8");
  if (!text.startsWith(KOPF) || !text.endsWith("</svg>")) {
    throw new Error(`ci/marke/icons/ui/${name}.svg hat nicht den Rumpf des CI-Sets`);
  }
  const kinder = text.slice(KOPF.length, -"</svg>".length).trim();
  if (/[{}]|-[a-z]+=|style=|class=/.test(kinder)) {
    throw new Error(`ci/marke/icons/ui/${name}.svg: Attribut, das als JSX nicht trägt`);
  }
  return kinder.replace(/ \/> </g, " /><");
}

export function erzeugen() {
  const zeilen = Object.entries(NAMEN).map(
    ([exp, name]) => `export const ${exp} = symbol("${name}", <>${inhalt(name)}</>);`,
  );
  return `// HB-SYMBOL — erzeugt von scripts/symbole-erzeugen.mjs aus ci/marke/icons/ui/, nicht von Hand ändern.
// Die Zeichen kommen aus dem CI-Set (aimighty-ci, marke/icons/ui/), Lucide 1.31.0, ISC.
import { symbol } from "@/components/symbol";

${zeilen.join("\n")}
`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const datei = join(frontend, "lib", "symbole.tsx");
  if (process.argv.includes("--pruefen")) {
    const gleich = readFileSync(datei, "utf8") === erzeugen();
    if (!gleich) console.error("lib/symbole.tsx ist nicht aus ci/marke/icons/ui/ erzeugt");
    process.exit(gleich ? 0 : 1);
  }
  writeFileSync(datei, erzeugen());
  console.log(`lib/symbole.tsx: ${Object.keys(NAMEN).length} Zeichen`);
}
