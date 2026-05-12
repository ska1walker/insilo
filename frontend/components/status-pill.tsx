import type { MeetingStatus } from "@/lib/api/meetings";

const LABEL: Record<MeetingStatus, string> = {
  draft: "Entwurf",
  uploading: "Wird übertragen",
  queued: "Wartet",
  transcribing: "Transkribiere",
  transcribed: "Transkribiert",
  summarizing: "Fasse zusammen",
  embedding: "Indexiere",
  ready: "Fertig",
  failed: "Fehlgeschlagen",
  archived: "Archiviert",
};

const TONE: Record<MeetingStatus, "neutral" | "live" | "ok" | "err"> = {
  draft: "neutral",
  uploading: "live",
  queued: "live",
  transcribing: "live",
  transcribed: "ok",
  summarizing: "live",
  embedding: "live",
  ready: "ok",
  failed: "err",
  archived: "neutral",
};

export function StatusPill({ status }: { status: MeetingStatus }) {
  const tone = TONE[status];
  if (tone === "err") {
    return (
      <span
        className="pill"
        style={{ background: "rgba(163, 58, 47, 0.08)", color: "var(--error)" }}
      >
        {LABEL[status]}
      </span>
    );
  }
  if (tone === "ok") {
    return (
      <span
        className="pill"
        style={{ background: "rgba(74, 124, 89, 0.08)", color: "var(--success)" }}
      >
        {LABEL[status]}
      </span>
    );
  }
  if (tone === "live") {
    return <span className="pill pill-recording">{LABEL[status]}</span>;
  }
  return <span className="pill">{LABEL[status]}</span>;
}
