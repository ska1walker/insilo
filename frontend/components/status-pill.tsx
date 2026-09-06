"use client";

import { useTranslations } from "next-intl";
import type { MeetingStatus } from "@/lib/api/meetings";

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
  const t = useTranslations("statusPill");
  const tone = TONE[status];
  const label = t(status);
  if (tone === "err") {
    return (
      <span
        className="pill"
        style={{ background: "var(--am-fehler-flaeche)", borderColor: "var(--am-fehler-rand)", color: "var(--am-fehler)" }}
      >
        {label}
      </span>
    );
  }
  if (tone === "ok") {
    return (
      <span
        className="pill"
        style={{ background: "var(--am-erfolg-flaeche)", borderColor: "var(--am-erfolg-rand)", color: "var(--am-erfolg)" }}
      >
        {label}
      </span>
    );
  }
  if (tone === "live") {
    return <span className="pill pill-recording">{label}</span>;
  }
  return <span className="pill">{label}</span>;
}
