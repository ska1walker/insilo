#!/usr/bin/env node
/**
 * Erzeugt alle Symbolgrößen aus den beiden SVG-Quellen.
 *
 *     node scripts/icons.mjs
 *
 * Warum ein Skript und nicht Handarbeit: in v0.1.68 war
 * `frontend/public/icons/` **leer**, während `manifest.json` drei Dateien
 * versprach — wer Insilo auf den Home-Bildschirm legte, bekam kein
 * Symbol. Eine einzelne Quelle und ein Befehl machen das
 * nachvollziehbar; eine neue Größe kostet eine Zeile in `ZIELE`, kein
 * Figma.
 *
 * Zwei Quellen, weil zwei Dinge verlangt werden:
 *
 * - `icon-quelle.svg` — mit Eckenrundung. Für alles, was das Symbol so
 *   zeigt, wie es gestaltet ist: Olares-Kachel, PWA-Symbol „any".
 * - `icon-maskable-quelle.svg` — randlos, ohne Rundung und ohne Kante.
 *   Android beschneidet maskable-Symbole auf beliebige Formen und setzt
 *   seine eigene Maske; eine mitgelieferte Rundung ergäbe einen
 *   doppelten Rand. Aus derselben Datei kommt das Apple-Touch-Symbol,
 *   denn iOS rundet ebenfalls selbst und geht mit Transparenz schlecht
 *   um.
 *
 * `sharp` liegt bereits im Frontend (Next.js bringt es mit) — deshalb
 * kommt keine weitere Abhängigkeit dazu.
 */

import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const WURZEL = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(join(WURZEL, "frontend/package.json"));
const sharp = require("sharp");

const QUELLEN = join(WURZEL, "frontend/public/icons");

/** [Quelle, Zieldatei, Kantenlänge, deckend?] */
const ZIELE = [
  // Olares: Markt-Kachel, Entrance-Symbol und featuredImage zeigen alle
  // auf die Datei in der Wurzel (siehe OlaresManifest).
  ["icon-quelle.svg", "icon.png", 512, false],
  // Wird ins Helm-Paket gelegt (siehe olares/.helmignore).
  ["icon-quelle.svg", "olares/icon-256.png", 256, false],
  // PWA — Zwecke „any"
  ["icon-quelle.svg", "frontend/public/icons/icon-512.png", 512, false],
  ["icon-quelle.svg", "frontend/public/icons/icon-192.png", 192, false],
  // Verknüpfungen im PWA-Manifest („Idee aufnehmen")
  ["icon-quelle.svg", "frontend/public/icons/icon-96.png", 96, false],
  // Android-Maske
  ["icon-maskable-quelle.svg", "frontend/public/icons/icon-maskable-512.png", 512, false],
  // iOS rundet selbst und mag keine Transparenz → deckend
  ["icon-maskable-quelle.svg", "frontend/public/icons/apple-touch-icon.png", 180, true],
];

// Grundton der Kachel — nur als Untergrund für das deckende Symbol.
const SAND = { r: 0xd6, g: 0xb2, b: 0x65, alpha: 1 };

for (const [quelle, ziel, kante, deckend] of ZIELE) {
  const svg = readFileSync(join(QUELLEN, quelle));
  // `density` hoch genug, damit die Weichzeichner-Filter sauber
  // aufgelöst werden, bevor verkleinert wird.
  let bild = sharp(svg, { density: 900 }).resize(kante, kante, {
    fit: "contain",
    background: { r: 0, g: 0, b: 0, alpha: 0 },
  });
  if (deckend) bild = bild.flatten({ background: SAND });
  const info = await bild.png({ compressionLevel: 9 }).toFile(join(WURZEL, ziel));
  console.log(`  ${ziel.padEnd(46)} ${info.width}×${info.height}  ${info.size} Bytes`);
}
