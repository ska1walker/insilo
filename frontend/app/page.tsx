"use client";

import { RecentMeetings } from "@/components/recent-meetings";
import { RecordingBlock } from "@/components/recording-block";
import { Seitentitel } from "@/components/seitentitel";
import { useTranslations } from "next-intl";

export default function Home() {
  const t = useTranslations("nav");
  return (
    <main className="mx-auto max-w-[var(--am-lesespalte)] px-6 py-12 md:px-12 md:py-16">
      {/* Die Startseite ist die Aufnahme — so ist sie auch in der Navigation gewählt. */}
      <Seitentitel className="mb-10">{t("record")}</Seitentitel>
      {/* Hero · Aufnahme-Block */}
      <section className="mb-16">
        <RecordingBlock variant="compact" />
      </section>

      {/* Trennlinie zwischen Aktion und Übersicht */}
      <hr className="my-12 border-0 border-t border-trennlinie" />

      {/* Zuletzt aufgenommen */}
      <RecentMeetings limit={5} />

      {/* Kein festes Datenschutz-Abzeichen hier: „bleibt auf der Box“ zeigt
          die Aufnahme oben gemessen, je nach Konfiguration. Ein Satz, der
          immer dasselbe sagt, wäre die ungemessene Null, die
          docs/DESIGN.md §5 ausschließt. */}
    </main>
  );
}
