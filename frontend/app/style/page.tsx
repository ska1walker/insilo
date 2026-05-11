"use client";

import { useState } from "react";

export default function Home() {
  const [recording, setRecording] = useState(false);

  return (
    <>
      {recording && <div className="recording-indicator" aria-hidden />}

      <main className="mx-auto max-w-[1280px] px-6 py-12 md:px-12 md:py-16">
        <header className="mb-24 flex items-center justify-between">
          <div className="flex items-baseline gap-3">
            <span className="font-display text-2xl font-medium tracking-tight">insilo</span>
            <span className="mono text-xs text-text-meta">v0.1.0 · phase 1</span>
          </div>
          <nav className="hidden gap-8 md:flex">
            <a className="btn-tertiary" href="#typography">Typografie</a>
            <a className="btn-tertiary" href="#colors">Farben</a>
            <a className="btn-tertiary" href="#components">Komponenten</a>
            <a className="btn-tertiary" href="#recording">Aufnahme</a>
          </nav>
        </header>

        <section className="mb-32">
          <p className="mono mb-6 text-xs uppercase tracking-[0.08em] text-text-meta">
            Phase 1 · MVP-Setup
          </p>
          <h1 className="mb-6 text-5xl font-medium leading-[1.1] md:text-6xl">
            Datensouveräne
            <br />
            Meeting-Intelligenz
          </h1>
          <p className="max-w-[640px] text-lg text-text-secondary md:text-xl">
            Aufnahme, Transkription und Analyse von Geschäftsgesprächen — vollständig
            auf der Hardware des Kunden. Keine Audiosekunde verlässt jemals die Box.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <button className="btn-primary" type="button">
              Erste Box anlegen
            </button>
            <a className="btn-secondary" href="https://github.com/ska1walker/insilo">
              Auf GitHub ansehen
            </a>
          </div>
        </section>

        <SectionDivider />

        <Section id="typography" eyebrow="01 · Typografie" title="Lexend Deca · Inter · JetBrains Mono">
          <div className="space-y-8">
            <Row label="H1 · Display">
              <h1 className="text-5xl font-medium leading-[1.1]">Geschäftsgespräche, intelligent erfasst</h1>
            </Row>
            <Row label="H2 · Section">
              <h2 className="text-3xl font-medium leading-tight">Wie funktioniert insilo?</h2>
            </Row>
            <Row label="H3 · Subsection">
              <h3 className="text-2xl font-medium">Aufnahme & Transkription</h3>
            </Row>
            <Row label="Body Large">
              <p className="text-[1.0625rem]">
                Die PWA nimmt Audio mit der MediaRecorder API auf und überträgt es
                verschlüsselt an die lokale Box im Serverraum.
              </p>
            </Row>
            <Row label="Body">
              <p>
                Whisper transkribiert in deutscher Sprache, pyannote.audio erkennt Sprecher
                automatisch. Alles im Hintergrund, ohne Cloud-Round-Trip.
              </p>
            </Row>
            <Row label="Meta · Caption">
              <p className="text-[0.8125rem] font-medium text-text-meta">
                Erstellt am 12. Mai 2026 · Zuletzt bearbeitet vor 3 Stunden
              </p>
            </Row>
            <Row label="Mono · Timestamp">
              <p className="mono text-[0.8125rem] text-text-meta">[00:14:32]</p>
            </Row>
            <Row label="Eyebrow · Uppercase Label">
              <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
                Meeting Details
              </p>
            </Row>
          </div>
        </Section>

        <SectionDivider />

        <Section id="colors" eyebrow="02 · Farbpalette" title="Weiß · Schwarz · Gold">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Swatch hex="#FFFFFF" name="white" role="Dominante Fläche" />
            <Swatch hex="#0A0A0A" name="black" role="Text · Struktur" />
            <Swatch hex="#C9A961" name="gold" role="Akzent · sehr sparsam" />
            <Swatch hex="#C84A3F" name="recording" role="Aufnahme-Status" />
            <Swatch hex="#FAFAF7" name="surface-soft" role="Cards · Sektionen" />
            <Swatch hex="#F5F3EE" name="surface-warm" role="Active panels" />
            <Swatch hex="#E8E6E1" name="border-subtle" role="Standard-Trennlinie" />
            <Swatch hex="#D4D1CA" name="border-strong" role="Akzentuierte Borders" />
          </div>
          <p className="mt-8 max-w-[640px] text-sm text-text-secondary">
            Gold trägt nur, wenn es selten ist. Niemals für primäre Buttons, niemals
            großflächig — ausschließlich für die Aufnahme-Linie, Sprecher-Labels,
            Selected-States und das Logo.
          </p>
        </Section>

        <SectionDivider />

        <Section id="components" eyebrow="03 · Komponenten" title="Reduziert. Klar. Vertrauenswürdig.">
          <div className="grid gap-12 md:grid-cols-2">
            <div>
              <Eyebrow>Buttons</Eyebrow>
              <div className="flex flex-wrap items-center gap-3">
                <button className="btn-primary" type="button">Aufnahme starten</button>
                <button className="btn-secondary" type="button">Abbrechen</button>
                <a className="btn-tertiary" href="#">Mehr erfahren</a>
              </div>
            </div>

            <div>
              <Eyebrow>Status-Pills</Eyebrow>
              <div className="flex flex-wrap items-center gap-3">
                <span className="pill">Entwurf</span>
                <span className="pill" style={{ background: "rgba(74, 124, 89, 0.08)", color: "var(--success)" }}>
                  Transkribiert
                </span>
                <span className="pill pill-recording">Live · 00:42</span>
              </div>
            </div>

            <div className="md:col-span-2">
              <Eyebrow>Meeting-Liste · PLAUD-Pattern</Eyebrow>
              <div className="overflow-hidden rounded-lg border border-border-subtle bg-white">
                <MeetingRow
                  title="Strategie-Klausur Q2"
                  meta="Mo, 12. Mai · 11:30 Uhr · 3 Sprecher"
                  duration="00:42:15"
                  selected
                />
                <MeetingRow
                  title="Vorstellungsgespräch — Frau Albers"
                  meta="Fr, 9. Mai · 14:00 Uhr · 2 Sprecher"
                  duration="00:54:08"
                />
                <MeetingRow
                  title="Beirat — vorbereitendes Gespräch"
                  meta="Do, 8. Mai · 16:30 Uhr · 4 Sprecher"
                  duration="01:12:44"
                />
              </div>
            </div>

            <div className="md:col-span-2">
              <Eyebrow>Speaker-Block · Transkript</Eyebrow>
              <div className="rounded-lg border border-border-subtle bg-white p-8">
                <SpeakerLine timestamp="[00:14:32]" speaker="MÜLLER">
                  Wir sollten bei der nächsten Sitzung das Thema Risikoabsicherung
                  intensiver besprechen.
                </SpeakerLine>
                <SpeakerLine timestamp="[00:14:48]" speaker="SCHMIDT">
                  Einverstanden. Ich bringe den aktuellen Stand der Compliance-Prüfung mit.
                </SpeakerLine>
                <SpeakerLine timestamp="[00:15:12]" speaker="MÜLLER">
                  Gut. Dann sehen wir uns am Donnerstag um zehn.
                </SpeakerLine>
              </div>
            </div>
          </div>
        </Section>

        <SectionDivider />

        <Section
          id="recording"
          eyebrow="04 · Die Identitäts-Kante"
          title="Goldene Pulse-Linie · der Premium-Moment"
        >
          <p className="mb-10 max-w-[640px] text-text-secondary">
            Klicken Sie auf den Aufnahme-Knopf — sehen Sie die 1px goldene Linie am oberen
            Bildschirmrand sanft pulsieren. Das ist die visuelle Signatur von insilo: subtil,
            sofort lesbar, ohne jeden Marketing-Lärm.
          </p>
          <div className="flex flex-col items-center gap-6">
            <button
              type="button"
              className={`btn-record ${recording ? "recording" : ""}`}
              onClick={() => setRecording((r) => !r)}
              aria-pressed={recording}
            >
              {recording ? "Stopp" : "Aufnehmen"}
            </button>
            <p className="mono text-xs text-text-meta">
              {recording ? "● Aufnahme läuft" : "Bereit"}
            </p>
          </div>
        </Section>

        <SectionDivider />

        <footer className="pt-16 pb-8">
          <div className="flex flex-col gap-4 text-sm text-text-meta md:flex-row md:items-center md:justify-between">
            <p>insilo · Datensouveräne Meeting-Intelligenz · © kaivo.studio</p>
            <p className="mono text-xs">Self-hosted on Olares · Made in Germany</p>
          </div>
        </footer>
      </main>
    </>
  );
}

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="py-24">
      <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">{eyebrow}</p>
      <h2 className="mb-12 text-3xl font-medium leading-tight md:text-4xl">{title}</h2>
      {children}
    </section>
  );
}

function SectionDivider() {
  return <hr className="border-0 border-t border-border-subtle" />;
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-4 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
      {children}
    </p>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-3 border-b border-border-subtle pb-6 last:border-b-0 md:grid-cols-[180px_1fr] md:items-baseline md:gap-8">
      <p className="mono text-xs uppercase tracking-[0.08em] text-text-meta">{label}</p>
      <div>{children}</div>
    </div>
  );
}

function Swatch({ hex, name, role }: { hex: string; name: string; role: string }) {
  const isLight = hex === "#FFFFFF" || hex.startsWith("#FA") || hex.startsWith("#F5") || hex.startsWith("#E8");
  return (
    <div className="rounded-lg border border-border-subtle bg-white p-4">
      <div
        className="mb-3 h-20 w-full rounded-md"
        style={{
          background: hex,
          border: isLight ? "1px solid var(--border-subtle)" : "none",
        }}
      />
      <p className="text-sm font-medium">{name}</p>
      <p className="mono text-xs text-text-meta">{hex}</p>
      <p className="mt-1 text-xs text-text-secondary">{role}</p>
    </div>
  );
}

function MeetingRow({
  title,
  meta,
  duration,
  selected,
}: {
  title: string;
  meta: string;
  duration: string;
  selected?: boolean;
}) {
  return (
    <div className={`meeting-row ${selected ? "selected" : ""}`}>
      <div className="min-w-0 flex-1">
        <p className="truncate text-base font-medium text-text-primary">{title}</p>
        <p className="mt-1 text-[0.8125rem] text-text-meta">{meta}</p>
      </div>
      <p className="mono shrink-0 text-[0.8125rem] font-medium text-text-meta">{duration}</p>
    </div>
  );
}

function SpeakerLine({
  timestamp,
  speaker,
  children,
}: {
  timestamp: string;
  speaker: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[80px_1fr] gap-4 py-3 md:grid-cols-[100px_1fr] md:gap-6">
      <div>
        <p className="mono text-[0.8125rem] font-medium text-text-meta">{timestamp}</p>
        <p
          className="mono mt-1 text-[0.8125rem] font-medium uppercase tracking-[0.02em]"
          style={{ color: "var(--gold)" }}
        >
          {speaker}
        </p>
      </div>
      <p className="text-base leading-relaxed text-text-primary">{children}</p>
    </div>
  );
}
