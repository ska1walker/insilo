import { RecordingBlock } from "@/components/recording-block";

export const metadata = {
  title: "Aufnahme · Insilo",
};

export default function AufnahmePage() {
  return (
    <main className="mx-auto flex min-h-[calc(100dvh-72px)] max-w-[640px] flex-col items-center justify-center px-6 py-16 md:px-12">
      <RecordingBlock variant="full" />
    </main>
  );
}
