/**
 * An das CRM weitergeben — der Schalter an der Vorlage.
 *
 * Anlass (0.1.102): Beacon übernahm jede Besprechung aus dem gemeinsamen
 * Ordner, auch interne Runden und Sprachnotizen. Welche Gespräche ins CRM
 * gehen, legt jetzt Insilo an der Vorlage fest.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { setzeWeitergabe } from "@/lib/api/templates";

const SPRACHEN = ["de", "en", "fr", "es", "it"] as const;

function nachrichten(sprache: string) {
  const pfad = fileURLToPath(new URL(`../messages/${sprache}.json`, import.meta.url));
  return JSON.parse(readFileSync(pfad, "utf8")) as {
    templatePrompts: Record<string, string>;
    protokoll: { aktionen: Record<string, string> };
  };
}

function antwort(status: number, koerper: unknown): Response {
  return new Response(JSON.stringify(koerper), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("setzeWeitergabe", () => {
  it("schickt nur die Markierung an den eigenen Endpunkt", async () => {
    const gerufen: Array<{ url: string; methode?: string; koerper: unknown }> = [];
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
      gerufen.push({ url, methode: init.method, koerper: JSON.parse(String(init.body)) });
      return antwort(200, { template_id: "t1", an_crm: false, an_crm_standard: true });
    });

    const ergebnis = await setzeWeitergabe("t1", false);

    expect(gerufen).toHaveLength(1);
    expect(gerufen[0].url).toContain("/api/v1/templates/t1/weitergabe");
    // Nicht über `/prompt`: ein Zurücksetzen des Prompts soll nicht
    // nebenbei ändern, was ins CRM geht.
    expect(gerufen[0].url).not.toContain("/prompt");
    expect(gerufen[0].methode).toBe("PUT");
    expect(gerufen[0].koerper).toEqual({ an_crm: false });
    expect(ergebnis.an_crm_standard).toBe(true);
  });

  it("reicht die Ablehnung der Box durch", async () => {
    vi.stubGlobal("fetch", async () =>
      antwort(403, {
        detail: "Welche Gespräche an das CRM gehen, legen nur Inhaberinnen und Verwaltende fest.",
      }),
    );

    const fehler = await setzeWeitergabe("t1", true).catch((e: unknown) => e);

    expect(fehler).toBeInstanceOf(ApiError);
    expect((fehler as ApiError).status).toBe(403);
  });
});

describe("Texte", () => {
  const schluessel = [
    "crmLabel",
    "crmHint",
    "crmStandard",
    "crmJa",
    "crmNein",
    "crmNurVerwaltung",
    "crmGespeichert",
    "crmEntfernt",
    "crmFehler",
    "tagCrm",
  ];

  it.each(SPRACHEN)("%s hat den Schalter vollständig", (sprache) => {
    const t = nachrichten(sprache).templatePrompts;
    for (const s of schluessel) {
      expect(t[s], `${sprache}.templatePrompts.${s}`).toBeTruthy();
    }
    expect(t.crmStandard).toContain("{wert}");
    expect(t.crmGespeichert).toContain("{name}");
  });

  it.each(SPRACHEN)("%s beschriftet den Vorgang im Protokoll", (sprache) => {
    // Die Umstellung steht im Protokoll (audit.py, `template.weitergabe`) —
    // ohne Beschriftung stünde dort der rohe Schlüssel.
    expect(nachrichten(sprache).protokoll.aktionen.template_weitergabe).toBeTruthy();
  });
});
