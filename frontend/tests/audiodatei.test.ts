import { describe, expect, it } from "vitest";
import { MAX_UPLOAD_MB, mimeFuerDatei, pruefeDatei, titelAusDateiname } from "@/lib/audiodatei";
import { dateinameVon, type AufnahmeKopf } from "@/lib/aufnahmen";

describe("mimeFuerDatei", () => {
  it("keeps a meaningful browser type", () => {
    expect(mimeFuerDatei("x.m4a", "audio/x-m4a")).toBe("audio/x-m4a");
    expect(mimeFuerDatei("x.wav", "audio/x-wav")).toBe("audio/x-wav");
  });

  it("treats audio-only video containers as audio (Chrome reports .webm as video/webm)", () => {
    expect(mimeFuerDatei("insilo-aufnahme-2026-09-14-0905.webm", "video/webm")).toBe("audio/webm");
    expect(mimeFuerDatei("sprachnotiz.3gp", "video/3gpp")).toBe("audio/3gpp");
    expect(mimeFuerDatei("x.opus", "audio/ogg")).toBe("audio/ogg");
  });

  it("derives the type from the extension when the browser says nothing", () => {
    expect(mimeFuerDatei("Besprechung.MP3", "")).toBe("audio/mpeg");
    expect(mimeFuerDatei("notiz.m4a", "application/octet-stream")).toBe("audio/mp4");
    expect(mimeFuerDatei("ohne", "")).toBe("");
  });
});

describe("pruefeDatei", () => {
  it("accepts audio up to the backend limit", () => {
    expect(pruefeDatei(MAX_UPLOAD_MB * 1024 * 1024, "audio/mpeg")).toBe("ok");
    expect(pruefeDatei(MAX_UPLOAD_MB * 1024 * 1024 + 1, "audio/mpeg")).toBe("zuGross");
    expect(pruefeDatei(10, "video/mp4")).toBe("ok");
  });

  it("refuses what is not audio", () => {
    expect(pruefeDatei(10, "application/pdf")).toBe("keinAudio");
    expect(pruefeDatei(10, "")).toBe("keinAudio");
  });

  it("refuses audio the box could neither store nor play back", () => {
    expect(pruefeDatei(10, "audio/amr")).toBe("keinAudio");
    expect(pruefeDatei(10, "video/webm")).toBe("keinAudio"); // only after mimeFuerDatei
  });

  it("accepts every type mimeFuerDatei produces for the offered extensions", () => {
    for (const name of ["a.webm", "a.m4a", "a.mp4", "a.aac", "a.ogg", "a.oga", "a.opus", "a.wav", "a.mp3", "a.flac", "a.3gp"]) {
      expect(pruefeDatei(10, mimeFuerDatei(name, ""))).toBe("ok");
    }
    expect(pruefeDatei(10, mimeFuerDatei("a.webm", "video/webm"))).toBe("ok");
    expect(pruefeDatei(10, mimeFuerDatei("a.m4a", "audio/x-m4a"))).toBe("ok");
    expect(pruefeDatei(10, mimeFuerDatei("a.wav", "audio/x-wav"))).toBe("ok");
  });
});

describe("titelAusDateiname", () => {
  it("gives a file saved by Insilo its original default title back", () => {
    const kopf = {
      begonnen: new Date(2026, 8, 14, 9, 5).getTime(),
      mimeType: "audio/webm;codecs=opus",
    } as AufnahmeKopf;
    const name = dateinameVon(kopf); // the same function that named the file
    expect(titelAusDateiname(name, "de", "Aufnahme vom")).toBe("Aufnahme vom 14.09. · 09:05");
  });

  it("uses the name without extension otherwise", () => {
    expect(titelAusDateiname("Jour fixe Vertrieb.m4a", "de", "Aufnahme vom")).toBe("Jour fixe Vertrieb");
    expect(titelAusDateiname("ohne-endung", "de", "Aufnahme vom")).toBe("ohne-endung");
    expect(titelAusDateiname(".m4a", "de", "Aufnahme vom")).toBe(".m4a");
  });
});
