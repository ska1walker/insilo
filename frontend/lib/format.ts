/**
 * Format-Layer für Insilo. Seit v0.1.43 locale-aware via Intl-APIs —
 * keine hartkodierten deutschen Monatsnamen mehr. Die Locale kommt
 * wahlweise als expliziter Parameter oder über next-intl.
 */

const PAD = (n: number) => n.toString().padStart(2, "0");

export function formatDuration(ms: number): string {
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0 ? `${PAD(h)}:${PAD(m)}:${PAD(s)}` : `${PAD(m)}:${PAD(s)}`;
}

/**
 * "Mo, 15. Mai · 14:30" / "Mon, 15 May · 14:30" — Wochentag (kurz),
 * Tag, Monat (kurz), Uhrzeit. Nutzt Intl.DateTimeFormat passend zur
 * Locale. Default-Locale ist "de" damit Aufrufer ohne expliziten
 * locale-Parameter bei einem Render auf der Server-Seite (ohne
 * next-intl-Context) ein stabiles Ergebnis bekommen.
 */
export function formatMeetingDate(ts: number, locale: string = "de"): string {
  const d = new Date(ts);
  const dayMon = new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(d);
  const time = new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
  return `${dayMon} · ${time}`;
}

/**
 * Default-Titel beim Aufzeichnungsstart, falls der User nichts eingibt.
 * "Aufnahme 15.05. · 14:30" / "Recording 05/15 · 2:30 PM" etc.
 */
export function defaultMeetingTitle(
  ts: number,
  locale: string = "de",
  recordingLabel: string = "Aufnahme",
): string {
  const d = new Date(ts);
  const dateShort = new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
  }).format(d);
  const time = new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
  return `${recordingLabel} ${dateShort} · ${time}`;
}

export function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}
