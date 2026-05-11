const PAD = (n: number) => n.toString().padStart(2, "0");

export function formatDuration(ms: number): string {
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0 ? `${PAD(h)}:${PAD(m)}:${PAD(s)}` : `${PAD(m)}:${PAD(s)}`;
}

const WEEKDAYS_DE = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const MONTHS_DE = [
  "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
  "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
];

export function formatMeetingDate(ts: number): string {
  const d = new Date(ts);
  const day = WEEKDAYS_DE[d.getDay()];
  const dom = d.getDate();
  const mon = MONTHS_DE[d.getMonth()];
  const time = `${PAD(d.getHours())}:${PAD(d.getMinutes())} Uhr`;
  return `${day}, ${dom}. ${mon} · ${time}`;
}

export function defaultMeetingTitle(ts: number): string {
  const d = new Date(ts);
  return `Aufnahme ${PAD(d.getDate())}.${PAD(d.getMonth() + 1)}. · ${PAD(d.getHours())}:${PAD(d.getMinutes())}`;
}

export function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}
