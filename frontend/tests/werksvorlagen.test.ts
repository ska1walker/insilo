import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { WERKSVORLAGEN } from "@/lib/werksvorlagen";

/**
 * Die Werksvorlagen in fünf Sprachen (lib/werksvorlagen.ts) und ihr
 * deutscher Wortlaut in der Datenbank (supabase/seed.sql) dürfen nicht
 * auseinanderlaufen: Wer seed.sql ändert, ändert messages/de.json mit.
 */

const FRONTEND = join(__dirname, "..");
const SEED = readFileSync(join(FRONTEND, "..", "supabase", "seed.sql"), "utf8");
const de = JSON.parse(readFileSync(join(FRONTEND, "messages", "de.json"), "utf8")).werksvorlagen;

function ausSeed(id: string): { name: string; beschreibung: string } {
  const m = SEED.match(new RegExp(`'${id}',\\s*\\n\\s*null,\\s*\\n\\s*'([^']+)',\\s*\\n\\s*'([^']+)'`));
  if (!m) throw new Error(`${id} nicht in seed.sql gefunden`);
  return { name: m[1], beschreibung: m[2] };
}

describe("Werksvorlagen", () => {
  it("jede Werksvorlage aus seed.sql hat ein Kürzel", () => {
    const ids = [...SEED.matchAll(/^\s*'(00000000-0000-0000-0000-0000000000\d\d)',\s*$/gm)].map((m) => m[1]);
    expect([...new Set(ids)].sort()).toEqual(Object.keys(WERKSVORLAGEN).sort());
  });

  it.each(Object.entries(WERKSVORLAGEN))("%s: messages/de.json gleicht seed.sql", (id, kuerzel) => {
    expect(de[kuerzel]).toEqual(ausSeed(id));
  });
});
