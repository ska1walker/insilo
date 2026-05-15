import Link from "next/link";
import { getTranslations } from "next-intl/server";
import {
  Brain,
  Building2,
  FileText,
  Lock,
  Mic,
  Search,
  Server,
  ShieldCheck,
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
    <main className="mx-auto max-w-[1080px] px-6 py-16 md:px-12 md:py-24">
      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="mb-28">
        <p className="mono mb-6 text-xs uppercase tracking-[0.08em] text-text-meta">
          {t("version")}
        </p>
        <h1 className="font-display text-[2.5rem] font-medium leading-[1.05] tracking-tight text-text-primary md:text-[3.5rem]">
          {t("heroTitle")}
        </h1>
        <p className="mt-8 max-w-[640px] text-lg leading-relaxed text-text-secondary md:text-xl">
          {t("heroBody")}
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <Link href="/aufnahme" className="btn-primary">
            {t("ctaPrimary")}
          </Link>
          <a href="#funktionen" className="btn-tertiary">
            {t("ctaSecondary")}
          </a>
        </div>
      </section>

      {/* ── Was Insilo macht ──────────────────────────────────────────── */}
      <section id="funktionen" className="mb-28">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
          {t("stepsLabel")}
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          {t("stepsTitle")}
        </h2>

        <div className="mt-14 grid gap-12 md:grid-cols-3">
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

      {/* ── Das Versprechen ───────────────────────────────────────────── */}
      <section className="mb-28">
        <div className="rounded-lg border border-border-subtle bg-surface-soft p-10 md:p-14">
          <div className="flex flex-col items-start gap-6 md:flex-row md:items-start md:gap-10">
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full"
              style={{
                background: "var(--gold-faint)",
                border: "1px solid rgba(201, 169, 97, 0.4)",
              }}
            >
              <ShieldCheck
                className="h-6 w-6"
                style={{ color: "var(--gold-deep)" }}
                strokeWidth={1.5}
              />
            </div>
            <div className="min-w-0">
              <p className="mono mb-2 text-xs uppercase tracking-[0.08em] text-text-meta">
                {t("promiseLabel")}
              </p>
              <h2 className="font-display text-2xl font-medium leading-tight tracking-tight md:text-3xl">
                {t("promiseTitle")}
              </h2>
              <p className="mt-4 max-w-[640px] text-text-secondary">
                {t("promiseBody")}
              </p>
              <ul className="mt-6 space-y-2 text-sm text-text-secondary">
                <SovereignBullet text={t("promise1")} />
                <SovereignBullet text={t("promise2")} />
                <SovereignBullet text={t("promise3")} />
                <SovereignBullet text={t("promise4")} />
                <SovereignBullet text={t("promise5")} />
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ── Für wen ───────────────────────────────────────────────────── */}
      <section className="mb-28">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
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

      {/* ── Tech in einem Satz ────────────────────────────────────────── */}
      <section className="mb-28">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
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

      {/* ── Identitäts-Detail ─────────────────────────────────────────── */}
      <section className="mb-28">
        <div className="rounded-lg border border-border-subtle bg-white p-10 md:p-14">
          <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
            {t("signatureLabel")}
          </p>
          <h2 className="font-display text-2xl font-medium leading-tight tracking-tight md:text-3xl">
            {t("signatureTitle")}
          </h2>
          <p className="mt-4 max-w-[640px] text-text-secondary">
            {t("signatureBody")}
          </p>
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────── */}
      <section className="border-t border-border-subtle pt-20 pb-8">
        <div className="flex flex-col items-start gap-6 md:flex-row md:items-end md:justify-between md:gap-10">
          <div>
            <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
              {t("finalTitle")}
            </h2>
            <p className="mt-3 max-w-[480px] text-text-secondary">
              {t("finalBody")}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/aufnahme" className="btn-primary">
              {t("finalCtaPrimary")}
            </Link>
            <Link href="/einstellungen" className="btn-secondary">
              {t("finalCtaSecondary")}
            </Link>
          </div>
        </div>
      </section>

      <footer className="mt-16">
        <div className="flex flex-col gap-3 border-t border-border-subtle pt-8 text-xs text-text-meta md:flex-row md:items-center md:justify-between">
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
        className="mb-5 flex h-9 w-9 items-center justify-center rounded-full text-text-primary"
        style={{
          background: "var(--surface-soft)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        {icon}
      </div>
      <h3 className="font-display text-lg font-medium tracking-tight text-text-primary">
        {title}
      </h3>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary">{body}</p>
    </div>
  );
}

function SovereignBullet({ text }: { text: string }) {
  return (
    <li className="flex items-baseline gap-3">
      <span
        className="mt-[0.4rem] inline-block h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: "var(--gold-deep)" }}
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
    <div className="border-l-2 border-border-subtle pl-5">
      <div className="flex items-center gap-2 text-text-primary">
        <span className="text-text-meta">{icon}</span>
        <p className="font-display text-base font-medium tracking-tight">
          {label}
        </p>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-text-secondary">{body}</p>
    </div>
  );
}

function ArchRow({ label, text }: { label: string; text: string }) {
  return (
    <>
      <p className="mono text-xs uppercase tracking-[0.08em] text-text-meta">
        {label}
      </p>
      <p className="text-text-secondary">{text}</p>
    </>
  );
}
