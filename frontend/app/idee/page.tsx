import { getTranslations } from "next-intl/server";
import { QuickCapture } from "@/components/quick-capture";

export async function generateMetadata() {
  const t = await getTranslations("nav");
  return { title: t("idee") };
}

export default function IdeePage() {
  return <QuickCapture />;
}
