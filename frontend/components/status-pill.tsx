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
        style={{ background: "rgba(163, 58, 47, 0.08)", color: "var(--error)" }}
      >
        {label}
      </span>
    );
  }
  if (tone === "ok") {
    return (
      <span
        className="pill"
        style={{ background: "rgba(74, 124, 89, 0.08)", color: "var(--success)" }}
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
