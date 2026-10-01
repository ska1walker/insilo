import { getTranslations } from "next-intl/server";
import { RecordingBlock } from "@/components/recording-block";
import { Seitentitel } from "@/components/seitentitel";

export async function generateMetadata() {
  const t = await getTranslations("nav");
  return { title: t("record") };
}

export default async function AufnahmePage() {
  const t = await getTranslations("nav");
  return (
    <main className="mx-auto flex min-h-[calc(100dvh-72px)] max-w-[640px] flex-col items-center justify-center px-6 py-16 md:px-12">
      <Seitentitel className="mb-10 text-center">{t("record")}</Seitentitel>
      <RecordingBlock variant="full" />
    </main>
  );
}
