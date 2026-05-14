import Link from "next/link";
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

export const metadata = {
  title: "Über Insilo · Datensouveräne Meeting-Intelligenz",
};

export default function UeberPage() {
  return (
    <main className="mx-auto max-w-[1080px] px-6 py-16 md:px-12 md:py-24">
      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="mb-28">
        <p className="mono mb-6 text-xs uppercase tracking-[0.08em] text-text-meta">
          Insilo · v0.1
        </p>
        <h1 className="font-display text-[2.5rem] font-medium leading-[1.05] tracking-tight text-text-primary md:text-[3.5rem]">
          Meeting-Intelligenz,
          <br />
          die niemals Ihr Haus verlässt.
        </h1>
        <p className="mt-8 max-w-[640px] text-lg leading-relaxed text-text-secondary md:text-xl">
          Insilo nimmt Geschäftsgespräche auf, transkribiert sie und erzeugt
          strukturierte Protokolle — vollständig auf Ihrer Olares-Box im
          Serverraum. Kein Cloud-Upload, keine Drittanbieter, keine Telemetrie.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <Link href="/aufnahme" className="btn-primary">
            Erste Aufnahme starten
          </Link>
          <a href="#funktionen" className="btn-tertiary">
            Wie es funktioniert ↓
          </a>
        </div>
      </section>

      {/* ── Was Insilo macht ──────────────────────────────────────────── */}
      <section id="funktionen" className="mb-28">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
          01 · Drei Schritte
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          Aufnehmen. Transkribieren. Verstehen.
        </h2>

        <div className="mt-14 grid gap-12 md:grid-cols-3">
          <FeatureBlock
            icon={<Mic className="h-5 w-5" strokeWidth={1.75} />}
            title="Aufnehmen"
            body="Im Browser, auf Mobile oder Desktop. Die PWA nutzt die MediaRecorder-API — drei Klicks, das Meeting läuft. Audio wird verschlüsselt zur Box übertragen und landet im hostPath."
          />
          <FeatureBlock
            icon={<FileText className="h-5 w-5" strokeWidth={1.75} />}
            title="Transkribieren"
            body="Whisper läuft auf der Box. Deutsche Sprache, ungefähr 30 Sekunden Verarbeitung pro Audio-Minute. Speaker-Diarization erkennt automatisch, wer spricht."
          />
          <FeatureBlock
            icon={<Brain className="h-5 w-5" strokeWidth={1.75} />}
            title="Verstehen"
            body="Ein lokales Sprachmodell erstellt strukturierte Protokolle nach Ihrer Vorlage. Fragen Sie später quer durch Ihr Meeting-Archiv — Antworten kommen mit Quellenangabe."
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
                02 · Das Versprechen
              </p>
              <h2 className="font-display text-2xl font-medium leading-tight tracking-tight md:text-3xl">
                Keine Audiosekunde verlässt jemals Ihre Box.
              </h2>
              <p className="mt-4 max-w-[640px] text-text-secondary">
                Audio, Transkript, Embeddings und Suchindex liegen auf der
                Hardware Ihrer Organisation. Insilo telefoniert nicht nach
                Hause. Wenn Sie ein externes Sprachmodell ansprechen wollen,
                entscheiden Sie das bewusst über die Einstellungen — sonst
                läuft alles ausschließlich lokal.
              </p>
              <ul className="mt-6 space-y-2 text-sm text-text-secondary">
                <SovereignBullet text="Audio bleibt im hostPath /app/data/audio/" />
                <SovereignBullet text="Transkripte in lokaler PostgreSQL" />
                <SovereignBullet text="Embeddings im pgvector der Box" />
                <SovereignBullet text="LLM-Aufrufe wahlweise an die lokale Olares-LiteLLM oder Ihren eigenen Endpunkt" />
                <SovereignBullet text="Keine Telemetrie, kein Phone Home, keine externen Schriften" />
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ── Für wen ───────────────────────────────────────────────────── */}
      <section className="mb-28">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
          03 · Zielgruppe
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          Für Organisationen, in denen Vertraulichkeit
          <br className="hidden md:block" /> kein Marketing-Versprechen ist.
        </h2>

        <div className="mt-12 grid gap-10 md:grid-cols-2">
          <PersonaBlock
            icon={<Lock className="h-4 w-4" strokeWidth={1.75} />}
            label="Anwaltskanzleien"
            body="Mandantengespräche unter Berufsgeheimnis. Keine Übertragung an Dritte — § 203 StGB-konform."
          />
          <PersonaBlock
            icon={<FileText className="h-4 w-4" strokeWidth={1.75} />}
            label="Steuerberatungen"
            body="Jahresgespräche, Mandantengeheimnis, DSGVO. Strukturierte Protokolle direkt aus dem Beratungstermin."
          />
          <PersonaBlock
            icon={<Search className="h-4 w-4" strokeWidth={1.75} />}
            label="Management-Beratung"
            body="Strategie-Sessions und Workshops. Erkenntnisse durchsuchbar machen, ohne dass Inhalte in fremden Clouds landen."
          />
          <PersonaBlock
            icon={<Building2 className="h-4 w-4" strokeWidth={1.75} />}
            label="Industrie-Mittelstand"
            body="Werkstor-Schutz für IP, Konstruktionsdetails und Lieferantenverhandlungen. Selbst-gehostete Infrastruktur, eigene Compliance."
          />
        </div>
      </section>

      {/* ── Tech in einem Satz ────────────────────────────────────────── */}
      <section className="mb-28">
        <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
          04 · Architektur
        </p>
        <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
          Standard-Bausteine. Saubere Trennung.
        </h2>

        <div className="mt-12 grid gap-y-6 text-sm leading-relaxed md:grid-cols-[180px_1fr] md:gap-x-10 md:gap-y-8">
          <ArchRow
            label="PWA"
            text="Next.js 15 (App Router, RSC). MediaRecorder API für die Aufnahme. Offline-fähig per Service Worker."
          />
          <ArchRow
            label="Backend"
            text="FastAPI, asyncpg gegen die Olares-System-PostgreSQL. Authentifizierung übernimmt Olares' Envoy-Sidecar — wir vertrauen dem X-Bfl-User-Header."
          />
          <ArchRow
            label="Transkription"
            text="faster-whisper mit large-v3, deutsche Sprache, optional pyannote.audio für Speaker-Diarization."
          />
          <ArchRow
            label="Sprachmodell"
            text="OpenAI-kompatibler Endpunkt. Default: die Olares-LiteLLM-Gateway-App. Alternative beliebig konfigurierbar unter Einstellungen."
          />
          <ArchRow
            label="Suche"
            text="BGE-M3-Embeddings (multilingual), pgvector zur Distanz-Suche, grounded Q&A mit Quellenmarkern."
          />
          <ArchRow
            label="Speicher"
            text="Audio im hostPath der Olares-Box. Transkripte, Templates und Org-Settings in PostgreSQL mit Row-Level-Security."
          />
        </div>
      </section>

      {/* ── Identitäts-Detail ─────────────────────────────────────────── */}
      <section className="mb-28">
        <div className="rounded-lg border border-border-subtle bg-white p-10 md:p-14">
          <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
            05 · Signatur
          </p>
          <h2 className="font-display text-2xl font-medium leading-tight tracking-tight md:text-3xl">
            Eine Pulse-Linie. Mehr nicht.
          </h2>
          <p className="mt-4 max-w-[640px] text-text-secondary">
            Während eine Aufnahme läuft, pulsiert eine 1-Pixel-dünne goldene
            Linie am oberen Bildschirmrand. Das ist die einzige visuelle
            Ankündigung. Sie ist sofort lesbar, ohne aufdringlich zu sein —
            und sie ist der Beweis, dass alle Vorgänge auf Ihrer Hardware
            laufen, weil nichts ist, was sich nicht zeigen lässt.
          </p>
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────── */}
      <section className="border-t border-border-subtle pt-20 pb-8">
        <div className="flex flex-col items-start gap-6 md:flex-row md:items-end md:justify-between md:gap-10">
          <div>
            <h2 className="font-display text-3xl font-medium leading-tight tracking-tight md:text-4xl">
              Bereit für die erste Aufnahme?
            </h2>
            <p className="mt-3 max-w-[480px] text-text-secondary">
              Dauert keine Minute. Sie sehen sofort, wie Transkription und
              Zusammenfassung auf Ihrer Box laufen — und können danach Ihre
              Vorlagen und Ihr Sprachmodell anpassen.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/aufnahme" className="btn-primary">
              Aufnahme starten
            </Link>
            <Link href="/einstellungen" className="btn-secondary">
              Einstellungen öffnen
            </Link>
          </div>
        </div>
      </section>

      <footer className="mt-16">
        <div className="flex flex-col gap-3 border-t border-border-subtle pt-8 text-xs text-text-meta md:flex-row md:items-center md:justify-between">
          <p>
            Insilo · Datensouveräne Meeting-Intelligenz · © kaivo.studio
          </p>
          <p className="mono inline-flex items-center gap-2">
            <Server className="h-3.5 w-3.5" strokeWidth={1.75} />
            Self-hosted auf Olares · Made in Germany
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
