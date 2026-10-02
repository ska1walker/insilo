// Insilo als installierbare App: Manifest, Symbole, Kopf der Seite.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { istIos } from "@/lib/installation";

const wurzel = join(__dirname, "..");
const manifest = JSON.parse(
  readFileSync(join(wurzel, "public/manifest.json"), "utf8"),
) as {
  id?: string;
  start_url: string;
  scope: string;
  display: string;
  icons: { src: string; sizes: string; purpose?: string }[];
  shortcuts: { url: string; description?: string; icons: { src: string }[] }[];
};

describe("Manifest", () => {
  it("trägt die Angaben, die Chrome zum Installieren verlangt", () => {
    expect(manifest.id).toBe("/");
    expect(manifest.start_url).toBe("/");
    expect(manifest.scope).toBe("/");
    expect(manifest.display).toBe("standalone");
    const groessen = manifest.icons.map((i) => i.sizes);
    expect(groessen).toContain("192x192");
    expect(groessen).toContain("512x512");
    expect(manifest.icons.some((i) => i.purpose === "maskable")).toBe(true);
  });

  it("verweist nur auf Dateien, die es gibt", () => {
    const pfade = [
      ...manifest.icons.map((i) => i.src),
      ...manifest.shortcuts.flatMap((s) => s.icons.map((i) => i.src)),
    ];
    for (const p of pfade) expect(existsSync(join(wurzel, "public", p)), p).toBe(true);
  });

  it("jede Verknüpfung führt auf eine Seite und sagt, was sie tut", () => {
    for (const s of manifest.shortcuts) {
      expect(existsSync(join(wurzel, "app", s.url, "page.tsx")), s.url).toBe(true);
      expect(s.description?.length).toBeGreaterThan(0);
    }
  });
});

describe("Kopf der Seite", () => {
  const layout = readFileSync(join(wurzel, "app/layout.tsx"), "utf8");

  it("lädt das Manifest mit Anmeldedaten (sonst antwortet der Olares-Login)", () => {
    expect(layout).toMatch(
      /<link rel="manifest" href="\/manifest.json" crossOrigin="use-credentials" \/>/,
    );
    // Nicht zusätzlich über die Metadaten — das wäre ein zweites Manifest ohne.
    expect(layout).not.toMatch(/^\s*manifest:/m);
  });

  it("öffnet auf iPhone und iPad im eigenen Fenster", () => {
    expect(layout).toMatch(/capable: true/);
    expect(layout).toMatch(/name="apple-mobile-web-app-capable" content="yes"/);
  });
});

describe("istIos", () => {
  it("erkennt iPhone und das iPad, das sich als Mac meldet", () => {
    expect(istIos("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)", 5)).toBe(true);
    expect(istIos("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", 5)).toBe(true);
  });

  it("hält einen Mac ohne Berührung und Android nicht für iOS", () => {
    expect(istIos("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", 0)).toBe(false);
    expect(istIos("Mozilla/5.0 (Linux; Android 14; Pixel 8)", 5)).toBe(false);
  });
});
