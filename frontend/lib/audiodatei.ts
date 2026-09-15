/**
 * Eine vorhandene Tonaufnahme hochladen — was vor dem Senden zu klären ist.
 *
 * Ohne Mikrofon, ohne Recorder: der Nutzer wählt eine Datei. Deren Typ
 * meldet der Browser uneinheitlich (das iPhone sagt `audio/x-m4a`, manche
 * Android-Dateiauswahl gar nichts), die Länge kennt er oft nicht, und der
 * Name kann ein von Insilo selbst gespeicherter sein
 * (`insilo-aufnahme-2026-09-14-0905.webm`, siehe `dateinameVon` in
 * `lib/aufnahmen.ts`). Das Backend korrigiert Endung und Dauer ohnehin
 * (`app/audioformat.py`, Dauer nach der Transkription) — hier geht es darum,
 * vorher sinnvoll abzulehnen und einen lesbaren Titel zu setzen.
 */
import { defaultMeetingTitle } from "@/lib/format";

/** Obergrenze des Backends (`settings.max_upload_mb`). */
export const MAX_UPLOAD_MB = 500;

const TYP_NACH_ENDUNG: Record<string, string> = {
  webm: "audio/webm",
  m4a: "audio/mp4",
  mp4: "audio/mp4",
  aac: "audio/aac",
  ogg: "audio/ogg",
  oga: "audio/ogg",
  opus: "audio/ogg",
  wav: "audio/wav",
  mp3: "audio/mpeg",
  flac: "audio/flac",
  "3gp": "audio/3gpp",
};

/** Für `<input accept>`: Typen und Endungen, weil Browser beides prüfen. */
export const ANNEHMBAR = [
  "audio/*",
  "video/mp4",
  ...Object.keys(TYP_NACH_ENDUNG).map((e) => `.${e}`),
].join(",");

function endung(name: string): string {
  const i = name.lastIndexOf(".");
  return i > 0 ? name.slice(i + 1).toLowerCase() : "";
}

/**
 * Der Typ, der ans Backend geht. Ein aussagekräftiger Audio-Typ bleibt.
 * Ein leerer, generischer oder `video/…`-Typ weicht dem, der zur Endung
 * passt — Chrome meldet `.webm` als `video/webm` und `.3gp` als
 * `video/3gpp`, auch wenn nur Ton darin ist. Ohne das lehnte der Knopf
 * ausgerechnet die Dateien ab, die „Als Datei speichern" erzeugt.
 */
export function mimeFuerDatei(name: string, typ: string): string {
  const t = typ.trim().toLowerCase();
  const nachEndung = TYP_NACH_ENDUNG[endung(name)];
  if (t.startsWith("audio/")) return t;
  if (nachEndung) return nachEndung;
  return t === "application/octet-stream" ? "" : t;
}

// Dieselben Kennungen wie `audio_endung` im Backend (`app/audioformat.py`).
// Was keine davon trägt, legte die Box als `.webm` ab und spielte es nicht ab.
const BEKANNT = [
  "webm", "m4a", "mp4", "aac", "ogg", "opus", "wav", "wave", "mpeg", "mp3", "flac", "3gpp",
];

export type Pruefung = "ok" | "zuGross" | "keinAudio";

export function pruefeDatei(groesse: number, mime: string): Pruefung {
  const audioArtig = mime.startsWith("audio/") || mime === "video/mp4";
  if (!audioArtig || !BEKANNT.some((k) => mime.includes(k))) return "keinAudio";
  if (groesse > MAX_UPLOAD_MB * 1024 * 1024) return "zuGross";
  return "ok";
}

const EIGENER_NAME = /^insilo-aufnahme-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})\./i;

function zeitAusEigenemNamen(name: string): number | null {
  const m = EIGENER_NAME.exec(name);
  if (!m) return null;
  const [, j, mo, t, h, mi] = m.map(Number);
  return new Date(j, mo - 1, t, h, mi).getTime();
}

/**
 * Wann eine Datei aufgenommen wurde, so gut der Browser es weiß: bei einer
 * von Insilo gespeicherten Aufnahme der Beginn aus dem Namen, sonst das
 * Änderungsdatum der Datei (bei Diktier-Apps meist das Ende der Aufnahme).
 * `undefined`, wenn beides fehlt — dann gilt der Upload.
 */
export function aufnahmeDatumFuerDatei(name: string, geaendert: number): number | undefined {
  const ausName = zeitAusEigenemNamen(name);
  if (ausName !== null) return ausName;
  return Number.isFinite(geaendert) && geaendert > 0 ? geaendert : undefined;
}

/**
 * Titel aus dem Dateinamen. Eine von Insilo gespeicherte Aufnahme bekommt
 * ihren ursprünglichen Standardtitel zurück; sonst der Name ohne Endung.
 */
export function titelAusDateiname(
  name: string,
  locale: string,
  praefix: string,
): string {
  const zeit = zeitAusEigenemNamen(name);
  if (zeit !== null) return defaultMeetingTitle(zeit, locale, praefix);
  const i = name.lastIndexOf(".");
  const ohneEndung = (i > 0 ? name.slice(0, i) : name).trim();
  return ohneEndung || name;
}

/**
 * Länge in Millisekunden aus den Metadaten, oder 0, wenn der Browser sie
 * nicht nennt. Nie länger als drei Sekunden: iOS lädt Metadaten oft gar
 * nicht, und ein Recorder-WebM meldet `Infinity`. 0 ist unschädlich — nach
 * der Transkription steht die gemessene Dauer in der Besprechung.
 */
export function dauerAusMetadaten(datei: Blob, wartenMs = 3000): Promise<number> {
  if (typeof document === "undefined") return Promise.resolve(0);
  const url = URL.createObjectURL(datei);
  const ton = document.createElement("audio");
  ton.preload = "metadata";
  return new Promise<number>((fertig) => {
    let erledigt = false;
    const ende = (ms: number) => {
      if (erledigt) return;
      erledigt = true;
      window.clearTimeout(uhr);
      ton.removeAttribute("src");
      ton.load();
      URL.revokeObjectURL(url);
      fertig(ms);
    };
    const uhr = window.setTimeout(() => ende(0), wartenMs);
    ton.onloadedmetadata = () =>
      ende(Number.isFinite(ton.duration) && ton.duration > 0 ? Math.round(ton.duration * 1000) : 0);
    ton.onerror = () => ende(0);
    ton.src = url;
  });
}
