/**
 * Die Verarbeitung erneut anstoßen.
 *
 * Anlass (0.1.99): Aufnahmen über etwa zwanzig Minuten scheiterten an
 * einem Zeitlimit. Danach lag die Aufnahme auf der Box, die Besprechung
 * stand auf „fehlgeschlagen" — und es gab keinen Weg, sie noch einmal
 * durch die Verarbeitung zu schicken. Für die Zusammenfassung gab es den
 * seit jeher, für die Erkennung nicht.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { retrySummary, retryTranscription } from "@/lib/api/meetings";
import { pollAbstandMs, pollAnzahl } from "@/lib/verarbeitung";

const SPRACHEN = ["de", "en", "fr", "es", "it"] as const;

function nachrichten(sprache: string): Record<string, Record<string, string>> {
  const pfad = fileURLToPath(new URL(`../messages/${sprache}.json`, import.meta.url));
  return JSON.parse(readFileSync(pfad, "utf8"));
}

/** Eine Antwort, wie `apiRequest` sie erwartet. */
function antwort(status: number, koerper: unknown): Response {
  return new Response(JSON.stringify(koerper), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("retryTranscription", () => {
  it("stößt genau den Endpunkt der Besprechung an", async () => {
    const gerufen: Array<[string, string | undefined]> = [];
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
      gerufen.push([url, init.method]);
      return antwort(202, { status: "queued" });
    });

    await retryTranscription("abc-123");

    expect(gerufen).toHaveLength(1);
    expect(gerufen[0][0]).toContain("/api/v1/meetings/abc-123/retry-transcription");
    expect(gerufen[0][1]).toBe("POST");
  });

  it("ist ein anderer Weg als die Zusammenfassung", async () => {
    // Sonst hätte der neue Knopf nur den alten Endpunkt noch einmal
    // gerufen — und die Erkennung liefe nie neu.
    const pfade: string[] = [];
    vi.stubGlobal("fetch", async (url: string) => {
      pfade.push(url);
      return antwort(202, { status: "queued" });
    });

    await retryTranscription("m1");
    await retrySummary("m1");

    expect(pfade[0]).not.toBe(pfade[1]);
    expect(pfade[0]).toContain("retry-transcription");
    expect(pfade[1]).toContain("retry-summary");
  });

  it("reicht die Begründung der Box durch", async () => {
    // 409 „wird schon verarbeitet" oder „keine Aufnahme mehr" — die
    // Oberfläche zeigt diesen Text, statt eine eigene Vermutung.
    vi.stubGlobal("fetch", async () =>
      antwort(409, { detail: "Diese Besprechung wird gerade verarbeitet." }),
    );

    const fehler = await retryTranscription("m1").catch((e: unknown) => e);

    expect(fehler).toBeInstanceOf(ApiError);
    expect((fehler as ApiError).status).toBe(409);
    expect((fehler as ApiError).body).toMatchObject({
      detail: "Diese Besprechung wird gerade verarbeitet.",
    });
  });
});

describe("Texte für den Fehlerblock", () => {
  const schluessel = [
    "retryTranscription",
    "retryTranscriptionHint",
    "retryTranscriptionFailed",
    "retrySummary",
    "retrying",
    "failedTitle",
  ];

  it.each(SPRACHEN)("%s hat alle Schlüssel", (sprache) => {
    const meeting = nachrichten(sprache).meeting;
    for (const s of schluessel) {
      expect(meeting[s], `${sprache}.meeting.${s}`).toBeTruthy();
    }
  });

  it.each(SPRACHEN)("%s markiert den Verweis auf die Einstellungen", (sprache) => {
    // Der Hinweis wird mit `t.rich` gerendert. Fehlt das Paar, steht dort
    // entweder kein Verweis oder ein sichtbares `<link>`.
    const hinweis = nachrichten(sprache).meeting.retryTranscriptionHint;
    expect(hinweis).toContain("<link>");
    expect(hinweis).toContain("</link>");
  });

  it("sagt, dass das Transkript dabei überschrieben wird", () => {
    // Die Verarbeitung von vorn wirft das vorhandene Transkript weg. Wer
    // das nicht liest, verliert womöglich nachbearbeitete Sprechernamen.
    expect(nachrichten("de").meeting.retryTranscriptionHint).toMatch(/überschrieben/);
    expect(nachrichten("en").meeting.retryTranscriptionHint).toMatch(/overwritten/);
  });
});

describe("Abfrage-Abstand während der Verarbeitung", () => {
  it("bleibt am Anfang schnell", () => {
    // Eine kurze Notiz ist in Sekunden fertig — da soll die Ansicht
    // sofort umspringen.
    expect(pollAbstandMs(0)).toBe(2000);
    expect(pollAbstandMs(20_000)).toBe(2000);
  });

  it("wird gemächlicher, je länger es dauert", () => {
    const stufen = [0, 60_000, 10 * 60_000, 60 * 60_000].map(pollAbstandMs);
    expect(stufen).toEqual([...stufen].sort((a, b) => a - b));
    expect(new Set(stufen).size).toBe(stufen.length);
  });

  it("hört bei einer halben Minute auf zu wachsen", () => {
    expect(pollAbstandMs(4 * 3600_000)).toBe(30_000);
  });

  it("macht aus vier Stunden Warten keine siebentausend Abfragen", () => {
    // Der Grund für die Staffelung: das harte Limit im Backend liegt bei
    // vier Stunden, vorher waren es dreißig Minuten.
    const vorher = (4 * 3600_000) / 2000;
    expect(vorher).toBeGreaterThan(7000);
    expect(pollAnzahl(4 * 3600_000)).toBeLessThan(600);
  });

  it("kostet eine kurze Verarbeitung nicht mehr als vorher", () => {
    expect(pollAnzahl(20_000)).toBe(10);
  });
});
