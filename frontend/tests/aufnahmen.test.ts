import { describe, expect, it } from "vitest";
import {
  dateinameVon,
  dauerVon,
  istVerwaist,
  VERWAIST_NACH_MS,
  type AufnahmeKopf,
} from "@/lib/aufnahmen";

const kopf = (teil: Partial<AufnahmeKopf> = {}): AufnahmeKopf => ({
  id: "a1",
  begonnen: new Date(2026, 8, 14, 9, 5).getTime(),
  zuletzt: new Date(2026, 8, 14, 10, 35).getTime(),
  mimeType: "audio/webm;codecs=opus",
  titel: "Aufnahme 14.09. · 09:05",
  stuecke: 5400,
  bytes: 90 * 1024 * 1024,
  dauerMs: null,
  ...teil,
});

describe("istVerwaist", () => {
  it("follows the lock when Web Locks are available", () => {
    const jetzt = kopf().zuletzt + 1;
    expect(istVerwaist(kopf(), new Set(["insilo-aufnahme-a1"]), jetzt)).toBe(false);
    // A lock for a different recording says nothing about this one.
    expect(istVerwaist(kopf(), new Set(["insilo-aufnahme-b2"]), jetzt)).toBe(true);
    // Without a lock it is orphaned, however fresh the last chunk is:
    // the tab that wrote it is gone.
    expect(istVerwaist(kopf(), new Set(), jetzt)).toBe(true);
  });

  it("falls back to the age of the last chunk without Web Locks", () => {
    const k = kopf();
    expect(istVerwaist(k, null, k.zuletzt + VERWAIST_NACH_MS)).toBe(false);
    expect(istVerwaist(k, null, k.zuletzt + VERWAIST_NACH_MS + 1)).toBe(true);
  });
});

describe("dauerVon", () => {
  it("prefers the measured duration", () => {
    expect(dauerVon(kopf({ dauerMs: 1234 }))).toBe(1234);
  });

  it("uses the span to the last chunk when the tab ended first", () => {
    expect(dauerVon(kopf())).toBe(90 * 60 * 1000);
    expect(dauerVon(kopf({ zuletzt: 0 }))).toBe(0);
  });
});

describe("dateinameVon", () => {
  it("names the file after the start and the container", () => {
    expect(dateinameVon(kopf())).toBe("insilo-aufnahme-2026-09-14-0905.webm");
    expect(dateinameVon(kopf({ mimeType: "audio/mp4;codecs=mp4a.40.2" }))).toMatch(/\.m4a$/);
    expect(dateinameVon(kopf({ mimeType: "audio/ogg;codecs=opus" }))).toMatch(/\.ogg$/);
  });
});
