import Link from "next/link";
import { getTranslations } from "next-intl/server";
import {
  ArrowDown,
  ArrowRight,
  Brain,
  Building2,
  Database,
  FileText,
  Globe,
  Lock,
  Mic,
  Search,
  Server,
  ShieldCheck,
  Star,
  Waves,
} from "lucide-react";

export async function generateMetadata() {
  const t = await getTranslations("about");
  return {
    title: t("metadataTitle"),
  };
}

export default async function UeberPage() {
  const t = await getTranslations("about");

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-16 md:px-12 md:py-24">
      {/* ── Hero — Split-Layout mit Transcript-Mock ─────────────────────── */}
      <section className="mb-32 grid items-start gap-12 md:grid-cols-[1.1fr_1fr] md:gap-16">
        <div>
          <p className="mono mb-6 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
            {t("version")}
          </p>
          <h1 className="font-display text-[2.5rem] font-medium leading-[1.05] tracking-tight text-text-primaer md:text-[3.75rem]">
            {t("heroTitle")}
          </h1>
          <p className="mt-8 max-w-[560px] text-lg leading-relaxed text-text-sekundaer md:text-xl">
            {t("heroBody")}
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Link href="/aufnahme" className="btn btn-primaer">
              {t("ctaPrimary")}
            </Link>
            <a href="#funktionen" className="btn btn-still">
              {t("ctaSecondary")}
            </a>
          </div>
        </div>
        <TranscriptMock t={t} />
      </section>

      {/* ── 02 · Sicherheit (Versprechen + Architektur + Compliance) ─── */}
      <section id="sicherheit" className="mb-32">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
          {t("promiseLabel")}
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          {t("promiseTitle")}
        </h2>
        <p className="mt-6 max-w-[720px] text-text-sekundaer">
          {t("promiseBody")}
        </p>

        <div className="mt-14 grid gap-12 md:grid-cols-[1.4fr_1fr] md:gap-16">
          <ArchitectureDiagram t={t} />
          <ComplianceList t={t} />
        </div>
      </section>

      {/* ── 03 · Sprecher-Erkennung (NEU) ────────────────────────────── */}
      <section id="sprecher" className="mb-32">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
          {t("speakerLabel")}
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          {t("speakerTitle")}
        </h2>
        <p className="mt-6 max-w-[720px] text-text-sekundaer">
          {t("speakerBody")}
        </p>

        <div className="mt-12 grid gap-10 md:grid-cols-[1.4fr_1fr] md:gap-16">
          <SpeakerCatalogMock t={t} />
          <ul className="space-y-3 text-sm text-text-sekundaer">
            <SovereignBullet text={t("speakerBullet1")} />
            <SovereignBullet text={t("speakerBullet2")} />
            <SovereignBullet text={t("speakerBullet3")} />
            <SovereignBullet text={t("speakerBullet4")} />
          </ul>
        </div>
      </section>

      {/* ── 04 · Drei Schritte (gekürzt) ─────────────────────────────── */}
      <section id="funktionen" className="mb-32">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
          {t("stepsLabel")}
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          {t("stepsTitle")}
        </h2>

        <div className="mt-12 grid gap-10 md:grid-cols-3">
          <FeatureBlock
            icon={<Mic className="h-5 w-5" strokeWidth={1.75} />}
            title={t("step1Title")}
            body={t("step1Body")}
          />
          <FeatureBlock
            icon={<FileText className="h-5 w-5" strokeWidth={1.75} />}
            title={t("step2Title")}
            body={t("step2Body")}
          />
          <FeatureBlock
            icon={<Brain className="h-5 w-5" strokeWidth={1.75} />}
            title={t("step3Title")}
            body={t("step3Body")}
          />
        </div>
      </section>

      {/* ── 05 · Zielgruppe ─────────────────────────────────────────── */}
      <section className="mb-32">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
          {t("audienceLabel")}
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          {t("audienceTitle")}
        </h2>

        <div className="mt-12 grid gap-10 md:grid-cols-2">
          <PersonaBlock
            icon={<Lock className="h-4 w-4" strokeWidth={1.75} />}
            label={t("personaLawTitle")}
            body={t("personaLawBody")}
          />
          <PersonaBlock
            icon={<FileText className="h-4 w-4" strokeWidth={1.75} />}
            label={t("personaTaxTitle")}
            body={t("personaTaxBody")}
          />
          <PersonaBlock
            icon={<Search className="h-4 w-4" strokeWidth={1.75} />}
            label={t("personaConsultTitle")}
            body={t("personaConsultBody")}
          />
          <PersonaBlock
            icon={<Building2 className="h-4 w-4" strokeWidth={1.75} />}
            label={t("personaIndustryTitle")}
            body={t("personaIndustryBody")}
          />
        </div>
      </section>

      {/* ── 06 · Architektur (kompakter) ────────────────────────────── */}
      <section className="mb-32 max-w-[820px]">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
          {t("archLabel")}
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          {t("archTitle")}
        </h2>

        <div className="mt-12 grid gap-y-6 text-sm leading-relaxed md:grid-cols-[180px_1fr] md:gap-x-10 md:gap-y-8">
          <ArchRow label={t("archPwaLabel")} text={t("archPwaText")} />
          <ArchRow label={t("archBackendLabel")} text={t("archBackendText")} />
          <ArchRow
            label={t("archTranscribeLabel")}
            text={t("archTranscribeText")}
          />
          <ArchRow label={t("archLlmLabel")} text={t("archLlmText")} />
          <ArchRow label={t("archSearchLabel")} text={t("archSearchText")} />
          <ArchRow label={t("archStorageLabel")} text={t("archStorageText")} />
        </div>
      </section>

      {/* ── 07 · Signatur (Gold-Linie) ──────────────────────────────── */}
      <section className="mb-32 max-w-[720px]">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
          {t("signatureLabel")}
        </p>
        <h2 className="font-display text-2xl font-medium leading-tight tracking-tight md:text-3xl">
          {t("signatureTitle")}
        </h2>
        <p className="mt-4 text-text-sekundaer">{t("signatureBody")}</p>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────── */}
      <section className="border-t border-trennlinie pt-20 pb-8">
        <div className="flex flex-col items-start gap-6 md:flex-row md:items-end md:justify-between md:gap-10">
          <div>
            <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
              {t("finalTitle")}
            </h2>
            <p className="mt-3 max-w-[480px] text-text-sekundaer">
              {t("finalBody")}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/aufnahme" className="btn btn-primaer">
              {t("finalCtaPrimary")}
            </Link>
            <Link href="/einstellungen" className="btn btn-sekundaer">
              {t("finalCtaSecondary")}
            </Link>
          </div>
        </div>
      </section>

      <footer className="mt-16">
        <div className="flex flex-col gap-3 border-t border-trennlinie pt-8 text-xs text-text-gedaempft md:flex-row md:items-center md:justify-between">
          <p>{t("footerLeft")}</p>
          <p className="mono inline-flex items-center gap-2">
            <Server className="h-3.5 w-3.5" strokeWidth={1.75} />
            {t("footerRight")}
          </p>
        </div>
      </footer>
    </main>
  );
}

// ─── Hilfs-Komponenten ─────────────────────────────────────────────────

type T = Awaited<ReturnType<typeof getTranslations<"about">>>;

/** Static transcript-snippet mock for the Hero — shows the product's
 *  visual language (speaker labels in gold, pulse-line at the top, mini
 *  summary below) without any interactivity. All strings i18n-driven. */
function TranscriptMock({ t }: { t: T }) {
  return (
    <div className="relative w-full overflow-hidden rounded-lg border border-trennlinie bg-seite">
      {/* Pulse-Goldlinie am oberen Rand — Brand-Signatur lokal simuliert.
          Animation-Keyframes `pulse-line` sind global in globals.css. */}
      <div
        aria-hidden
        className="h-px w-full"
        style={{
          background: "var(--am-gold-500)",
          animation: "pulse-line 2.4s ease-in-out infinite",
        }}
      />

      <div className="px-6 pt-5 pb-1">
        <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-gedaempft">
          {t("heroMockEyebrow")}
        </p>
      </div>

      {/* Transcript-Segments — Layout & Type folgt docs/DESIGN.md §5 */}
      <div className="px-6 py-4">
        <MockSegment
          time={t("heroMockSpeaker1Time")}
          speaker={t("heroMockSpeaker1Name")}
          text={t("heroMockSpeaker1Text")}
        />
        <MockSegment
          time={t("heroMockSpeaker2Time")}
          speaker={t("heroMockSpeaker2Name")}
          text={t("heroMockSpeaker2Text")}
        />
      </div>

      <div className="border-t border-trennlinie bg-flaeche-1 px-6 py-5">
        <p className="mono mb-2 text-[0.6875rem] uppercase tracking-[0.08em] text-text-gedaempft">
          {t("heroMockSummaryLabel")}
        </p>
        <ul className="space-y-1.5 text-sm text-text-primaer">
          <li className="flex items-baseline gap-2">
            <span
              aria-hidden
              className="mt-[0.4rem] inline-block h-1 w-1 shrink-0 rounded-full"
              style={{ background: "var(--am-text-sekundaer)" }}
            />
            <span>{t("heroMockSummary1")}</span>
          </li>
          <li className="flex items-baseline gap-2">
            <span
              aria-hidden
              className="mt-[0.4rem] inline-block h-1 w-1 shrink-0 rounded-full"
              style={{ background: "var(--am-text-sekundaer)" }}
            />
            <span>{t("heroMockSummary2")}</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

function MockSegment({
  time,
  speaker,
  text,
}: {
  time: string;
  speaker: string;
  text: string;
}) {
  return (
    <div className="grid grid-cols-[88px_1fr] gap-3 py-3">
      <div>
        <p className="mono text-[0.75rem] font-medium text-text-gedaempft">{time}</p>
        <p
          className="mono mt-1 text-[0.75rem] font-medium uppercase tracking-[0.04em]"
          style={{ color: "var(--am-gold-beschriftung)" }}
        >
          {speaker}
        </p>
      </div>
      <p className="text-[0.9375rem] leading-relaxed text-text-primaer">
        {text}
      </p>
    </div>
  );
}

/** Horizontal pipeline diagram: Browser → Box-API → Whisper → PostgreSQL
 *  with LLM as a branch. Pure CSS/Lucide-Icons, no SVG asset.
 *  Mobile: stacks vertically with ArrowDown icons. */
function ArchitectureDiagram({ t }: { t: T }) {
  const boxes = [
    { label: t("archDiagramBrowser"), icon: <Globe className="h-4 w-4" strokeWidth={1.75} /> },
    { label: t("archDiagramApi"), icon: <Server className="h-4 w-4" strokeWidth={1.75} /> },
    { label: t("archDiagramWhisper"), icon: <Mic className="h-4 w-4" strokeWidth={1.75} /> },
    { label: t("archDiagramDb"), icon: <Database className="h-4 w-4" strokeWidth={1.75} /> },
  ];

  return (
    <div>
      <p className="mono mb-5 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
        {t("archDiagramTitle")}
      </p>

      {/* Horizontal flow — md+ */}
      <div className="hidden md:flex items-center gap-2">
        {boxes.map((b, i) => (
          <DiagramRow key={i} icon={b.icon} label={b.label} isLast={i === boxes.length - 1} arrowDir="right" />
        ))}
      </div>

      {/* LLM branch — md+ — sitzt unter „Box-API", einfach unterhalb gerendert */}
      <div className="hidden md:flex items-start gap-2 mt-3 pl-[calc(120px+1rem)]">
        <ArrowDown className="h-4 w-4 text-text-gedaempft" strokeWidth={1.5} />
        <div
          className="inline-flex items-center gap-2 rounded-md border border-trennlinie px-3 py-2 text-sm text-text-primaer"
          style={{ background: "var(--am-seite)" }}
        >
          <Brain className="h-4 w-4" strokeWidth={1.75} />
          {t("archDiagramLlm")}
        </div>
      </div>

      {/* Vertical flow — mobile */}
      <div className="md:hidden flex flex-col gap-2">
        {boxes.map((b, i) => (
          <DiagramRow key={i} icon={b.icon} label={b.label} isLast={i === boxes.length - 1} arrowDir="down" />
        ))}
        <ArrowDown className="h-4 w-4 text-text-gedaempft self-center" strokeWidth={1.5} />
        <div
          className="inline-flex items-center gap-2 rounded-md border border-trennlinie px-3 py-2 text-sm text-text-primaer self-start"
          style={{ background: "var(--am-seite)" }}
        >
          <Brain className="h-4 w-4" strokeWidth={1.75} />
          {t("archDiagramLlm")}
        </div>
      </div>

      <p className="mt-6 text-xs text-text-gedaempft">{t("archDiagramCaption")}</p>
    </div>
  );
}

function DiagramRow({
  icon,
  label,
  isLast,
  arrowDir,
}: {
  icon: React.ReactNode;
  label: string;
  isLast: boolean;
  arrowDir: "right" | "down";
}) {
  return (
    <>
      <div
        className="inline-flex items-center gap-2 rounded-md border border-trennlinie px-3 py-2 text-sm text-text-primaer"
        style={{ background: "var(--am-seite)" }}
      >
        {icon}
        {label}
      </div>
      {!isLast &&
        (arrowDir === "right" ? (
          <ArrowRight className="h-4 w-4 text-text-gedaempft" strokeWidth={1.5} />
        ) : (
          <ArrowDown className="h-4 w-4 text-text-gedaempft self-center" strokeWidth={1.5} />
        ))}
    </>
  );
}

function ComplianceList({ t }: { t: T }) {
  return (
    <div>
      <p className="mono mb-5 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
        {t("complianceTitle")}
      </p>
      <ul className="space-y-3 text-sm text-text-sekundaer">
        <SovereignBullet text={t("compliance1")} />
        <SovereignBullet text={t("compliance2")} />
        <SovereignBullet text={t("compliance3")} />
        <SovereignBullet text={t("compliance4")} />
      </ul>
    </div>
  );
}

/** Static visual clone of cluster-assignment-panel rows (lines 149-228)
 *  — gold speaker labels, automatic/manual pills, match-score chip,
 *  star for is_self. No API call, no interactivity. */
function SpeakerCatalogMock({ t }: { t: T }) {
  return (
    <div className="rounded-lg border border-trennlinie bg-flaeche-1 p-4">
      <p className="mono mb-3 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-gedaempft">
        <Waves className="mr-1.5 inline h-3 w-3" strokeWidth={1.75} />
        {t("speakerMockSectionLabel")}
      </p>

      <div className="space-y-2">
        <SpeakerMockRow
          cluster={t("speakerMockCluster00")}
          name={t("speakerMockNameSelf")}
          match={t("speakerMockMatchAuto")}
          score="92"
          isSelf
          assignment="auto"
        />
        <SpeakerMockRow
          cluster={t("speakerMockCluster01")}
          name={t("speakerMockNameOther")}
          match={t("speakerMockMatchManual")}
          assignment="manual"
        />
        <SpeakerMockRow
          cluster={t("speakerMockCluster02")}
          name={t("speakerMockUnassigned")}
          unassigned
        />
      </div>
    </div>
  );
}

function SpeakerMockRow({
  cluster,
  name,
  match,
  score,
  isSelf,
  assignment,
  unassigned,
}: {
  cluster: string;
  name: string;
  match?: string;
  score?: string;
  isSelf?: boolean;
  assignment?: "auto" | "manual";
  unassigned?: boolean;
}) {
  return (
    <div className="rounded-md bg-seite px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-gedaempft">
          {cluster}
        </span>
        {isSelf && (
          <Star
            className="h-3 w-3"
            strokeWidth={2}
            style={{ color: "var(--am-gold-500)" }}
            aria-hidden
          />
        )}
        {unassigned ? (
          <span className="mono text-[0.8125rem] font-medium uppercase tracking-[0.02em] text-text-gedaempft">
            {name}
          </span>
        ) : (
          <span
            className="mono text-[0.8125rem] font-medium uppercase tracking-[0.02em]"
            style={{ color: "var(--am-gold-beschriftung)" }}
          >
            {name}
          </span>
        )}
        {score && (
          <span
            className="rounded-full bg-flaeche-1 px-2 py-0.5 text-[0.6875rem] uppercase tracking-[0.04em] text-text-gedaempft"
            title="Auto-Match Cosine-Similarity"
          >
            {score}%
          </span>
        )}
        {match && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[0.6875rem] uppercase tracking-[0.04em]"
            style={
              assignment === "auto"
                ? {
                    background: "rgba(74,124,89,0.08)",
                    color: "var(--am-erfolg)",
                  }
                : {
                    background: "var(--am-flaeche-1)",
                    color: "var(--am-text-gedaempft)",
                  }
            }
          >
            {match}
          </span>
        )}
      </div>
    </div>
  );
}

function FeatureBlock({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div>
      <div
        className="mb-5 flex h-9 w-9 items-center justify-center rounded-full text-text-primaer"
        style={{
          background: "var(--am-flaeche-1)",
          border: "1px solid var(--am-trennlinie)",
        }}
      >
        {icon}
      </div>
      <h3 className="font-display text-lg font-medium tracking-tight text-text-primaer">
        {title}
      </h3>
      <p className="mt-3 text-sm leading-relaxed text-text-sekundaer">{body}</p>
    </div>
  );
}

function SovereignBullet({ text }: { text: string }) {
  return (
    <li className="flex items-baseline gap-3">
      <span
        className="mt-[0.4rem] inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: "var(--am-gold-800)" }}
        aria-hidden
      />
      <span>{text}</span>
    </li>
  );
}

function PersonaBlock({
  icon,
  label,
  body,
}: {
  icon: React.ReactNode;
  label: string;
  body: string;
}) {
  return (
    <div className="border-l-2 border-trennlinie pl-5">
      <div className="flex items-center gap-2 text-text-primaer">
        <span className="text-text-gedaempft">{icon}</span>
        <p className="font-display text-base font-medium tracking-tight">
          {label}
        </p>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-text-sekundaer">{body}</p>
    </div>
  );
}

function ArchRow({ label, text }: { label: string; text: string }) {
  return (
    <>
      <p className="mono text-xs uppercase tracking-[0.08em] text-text-gedaempft">
        {label}
      </p>
      <p className="text-text-sekundaer">{text}</p>
    </>
  );
}
