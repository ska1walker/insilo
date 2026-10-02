"use client";

import { useTranslations } from "next-intl";
import type { MeetingStatus } from "@/lib/api/meetings";

/**
 * Der Zustand einer Besprechung als HB-PILLE in der Zustandsfassung
 * (CI ABGLEICH IN-B5, seit ci-26.10.10): ohne Zustand „wartet“, sonst
 * läuft (Gold), erledigt oder gescheitert — immer Punkt und Wort.
 */
const ZUSTAND: Record<MeetingStatus, "laeuft" | "erfolg" | "fehler" | undefined> = {
  draft: undefined,
  uploading: "laeuft",
  queued: "laeuft",
  transcribing: "laeuft",
  transcribed: "erfolg",
  summarizing: "laeuft",
  embedding: "laeuft",
  ready: "erfolg",
  failed: "fehler",
  archived: undefined,
};

export function StatusPill({ status }: { status: MeetingStatus }) {
  const t = useTranslations("statusPill");
  return (
    <span className="stufe" data-zustand={ZUSTAND[status]}>
      {t(status)}
    </span>
  );
}
