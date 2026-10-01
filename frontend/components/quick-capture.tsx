"use client";

import { ArrowLeft, CheckCircle2, Loader2, Lokal, Mic, Square } from "@/lib/symbole";
import { useEgress } from "@/lib/api/egress";
import { Aufnahmezeichen } from "@/components/symbol";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { AufnahmeWelle } from "@/components/aufnahme-welle";
import { useFortschrittText, useSendefehler } from "@/components/offene-aufnahmen";
import type { Fortschritt } from "@/lib/api/hochladen";
import { ASR_AUDIO_CONSTRAINTS, ASR_RECORDER_OPTIONS } from "@/lib/audio";
import {
  alsDateiSpeichern,
  alsGescheitertAblegen,
  gescheitertErledigt,
  senden,
  Sicherung,
  type Gescheitert,
} from "@/lib/aufnahmen";
import { defaultMeetingTitle, formatDuration } from "@/lib/format";
import { useWachhalten } from "@/lib/wachhalten";

const PREFERRED_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

function pickMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  for (const t of PREFERRED_MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return null;
}

type Phase =
  | "idle"
  | "requesting"
  | "recording"
  | "saving"
  | "saved"
  | "denied"
  | "unsupported"
  | "error";

const SAVED_AUTO_RESET_MS = 5000;

// Die dunkle Car-Mode-Palette, aus den Token (Blau 950/25, Gold
// 500/300/700). Die laufende Aufnahme trägt Gold, nicht Rot: Rot bleibt dem
// Fehler vorbehalten (docs/DESIGN.md §3).
const COLORS = {
  black: "var(--am-blau-950)",
  white: "var(--am-blau-25)",
  gold: "var(--am-gold-500)",
  goldLight: "var(--am-gold-300)",
  goldDeep: "var(--am-gold-700)",
  recording: "var(--am-gold-500)",
} as const;


/**
 * Schauerfunktion — Car-Mode-Aufnahme für unterwegs (auto, walking, shower).
 *
 * UX-Ziel: Spotify Car-Mode auf Insilo-Niveau. Dunkler Vollbild-BG mit
 * subtilem Gold-Vignette, ein einziger Riesen-Button mittig (Gold), sonst
 * nur die nötigsten Statuszeilen. State-Maschine:
 *   idle → recording → saving → saved (5 s Auto-Reset) → idle
 *
 * Kein Template-Picker, keine Sprach-Auswahl, kein Save-Button. Aufnahme
 * landet als `quick_mode=true` im Backend, das Backend setzt das
 * Schnellnotiz-Template (00000005) automatisch und forciert die
 * Webhook-Auto-Dispatch (siehe notify.py).
 *
 * Dark-Mode-Transition: `body.quick-capture-active`-Klasse wird beim
 * Mount toggled, CSS in globals.css macht den smooth Fade-to-Black und
 * blendet den Insilo-Header aus. Reduced-motion respektieren.
 *
 * Vibrations-Feedback auf mobilen Geräten beim Start/Stopp + Wake-Lock,
 * damit der Bildschirm während der Aufnahme nicht ausgeht.
 */
export function QuickCapture() {
  const t = useTranslations("quickCapture");
  const egress = useEgress();
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // Die Welle braucht den Stream als Wert, nicht als Ref.
  const [liveStream, setLiveStream] = useState<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const tickRef = useRef<number | null>(null);
  const savedResetRef = useRef<number | null>(null);
  const sicherungRef = useRef<Sicherung | null>(null);
  const aktivRef = useRef(true);
  const tAufnahme = useTranslations("aufnahmeSicherung");
  const sendefehler = useSendefehler();
  // Die zuletzt gescheiterte Notiz, wie sie hier angeboten wird. Sie
  // gehört der Liste in `lib/aufnahmen.ts`: startet jemand die nächste oder
  // verlässt die Ansicht, bleibt sie dort und erscheint über den Ansichten.
  const [gescheitert, setGescheitert] = useState<Gescheitert | null>(null);
  const [sendetErneut, setSendetErneut] = useState(false);
  const [fortschritt, setFortschritt] = useState<Fortschritt | null>(null);
  const fortschrittText = useFortschrittText();

  // Wach bleiben, solange aufgenommen oder gesendet wird. Bis 0.1.96 gab die
  // Notiz die Sperre vor dem Senden frei — und holte sie nach einem kurzen
  // Verdecken des Tabs nie zurück (siehe `lib/wachhalten.ts`).
  useWachhalten(phase === "recording" || phase === "saving" || sendetErneut);

  // Dark-Mode-Transition: body-class steuert globalen Fade. globals.css
  // versteckt zusätzlich den normalen Insilo-Header während aktiv.
  useEffect(() => {
    document.body.classList.add("quick-capture-active");
    return () => document.body.classList.remove("quick-capture-active");
  }, []);

  // Cleanup all browser resources on unmount.
  useEffect(() => {
    aktivRef.current = true;
    return () => {
      aktivRef.current = false;
      stopTracksAndTick();
      if (savedResetRef.current !== null) {
        window.clearTimeout(savedResetRef.current);
      }
      sicherungRef.current?.loslassen();
    };
  }, []);

  // Gescheiterte Notizen bewacht die Liste in der Hülle.
  const ungesichert = phase === "recording" || phase === "saving";
  useEffect(() => {
    if (!ungesichert) return;
    const warnen = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = ""; // Safari fragt nur mit gesetztem returnValue
    };
    window.addEventListener("beforeunload", warnen);
    return () => window.removeEventListener("beforeunload", warnen);
  }, [ungesichert]);

  function stopTracksAndTick() {
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
      setLiveStream(null);
    }
  }

  function vibrate(pattern: number | number[]) {
    if (typeof navigator !== "undefined" && "vibrate" in navigator) {
      try {
        navigator.vibrate(pattern);
      } catch {
        /* ignore */
      }
    }
  }

  async function startRecording() {
    setError(null);
    // Hartes Reset falls noch ein "saved"-Timer läuft.
    if (savedResetRef.current !== null) {
      window.clearTimeout(savedResetRef.current);
      savedResetRef.current = null;
    }
    const mime = pickMimeType();
    if (!mime) {
      setPhase("unsupported");
      return;
    }
    // Eine liegen gebliebene Notiz bleibt in der Liste über den Ansichten.
    setGescheitert(null);
    setPhase("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: ASR_AUDIO_CONSTRAINTS,
      });
      streamRef.current = stream;
      setLiveStream(stream);
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream, {
        mimeType: mime,
        ...ASR_RECORDER_OPTIONS,
      });
      const sicherung = await Sicherung.beginnen({
        mimeType: mime,
        titel: defaultMeetingTitle(Date.now(), locale, t("defaultTitlePrefix")),
        quickMode: true,
      });
      sicherungRef.current = sicherung;
      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) {
          chunksRef.current.push(ev.data);
          sicherung.anhaengen(ev.data);
        }
      };
      recorder.start(1000);
      recorderRef.current = recorder;
      startedAtRef.current = Date.now();
      setElapsed(0);
      setPhase("recording");
      vibrate(50);
      tickRef.current = window.setInterval(() => {
        setElapsed(Date.now() - startedAtRef.current);
      }, 250);
    } catch (err) {
      stopTracksAndTick();
      void sicherungRef.current?.absagen();
      sicherungRef.current = null;
      const name = (err as DOMException)?.name;
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setPhase("denied");
      } else {
        setPhase("idle");
        setError(t("micStartFailed"));
      }
    }
  }

  async function stopAndSave() {
    const recorder = recorderRef.current;
    if (!recorder) return;
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    const durationMs = Date.now() - startedAtRef.current;
    setPhase("saving");
    vibrate([100, 50, 100]);

    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      recorder.stop();
    });

    stopTracksAndTick();

    const sicherung = sicherungRef.current;
    sicherungRef.current = null;
    if (!sicherung) return;
    const mimeType = recorder.mimeType || sicherung.kopf.mimeType;
    const ton = new Blob(chunksRef.current, { type: mimeType });
    chunksRef.current = [];
    await sicherung.abschliessen(durationMs, mimeType);

    try {
      await senden(sicherung.kopf, ton, setFortschritt);
      sicherung.loslassen();
      if (aktivRef.current) gesendet();
    } catch (err) {
      console.error("upload failed", err);
      const eintrag = { sicherung, ton, fehler: sendefehler(err) };
      alsGescheitertAblegen(eintrag);
      if (!aktivRef.current) return;
      setPhase("error");
      setError(eintrag.fehler);
      setGescheitert(eintrag);
    } finally {
      setFortschritt(null);
    }
  }

  function gesendet() {
    setPhase("saved");
    savedResetRef.current = window.setTimeout(() => {
      setPhase("idle");
      setElapsed(0);
      savedResetRef.current = null;
    }, SAVED_AUTO_RESET_MS);
  }

  async function erneutSenden() {
    if (!gescheitert) return;
    setSendetErneut(true);
    setError(null);
    try {
      await senden(gescheitert.sicherung.kopf, gescheitert.ton, setFortschritt);
      gescheitertErledigt(gescheitert.sicherung.kopf.id);
      if (!aktivRef.current) return;
      setGescheitert(null);
      gesendet();
    } catch (err) {
      console.error("upload retry failed", err);
      setError(sendefehler(err));
    } finally {
      setSendetErneut(false);
      setFortschritt(null);
    }
  }

  const bgStyle = {
    backgroundColor: COLORS.black,
    color: COLORS.white,
  };

  return (
    <div
      // .quick-capture-shell in globals.css setzt background-color via
      // !important — Tailwind-Class und inline-style haben in v0.1.53-55
      // trotz korrektem Bundle nicht durchgesetzt. Diese Klasse ist
      // idiot-proof. Kein Verlauf mehr (CI kern/nicht.md, ABGLEICH IN-R6).
      className="quick-capture-shell immersive-in fixed inset-0 z-50 flex flex-col"
      style={bgStyle}
    >
      {/* Top bar — minimal, back-arrow links + eyebrow label.
          Back-Arrow mit explizitem Border + helleren Fill, sodass er
          auch dann sichtbar ist wenn der Dark-BG nicht durchschlägt. */}
      <header className="flex items-center justify-between px-6 pt-[max(env(safe-area-inset-top),1.5rem)] pb-2 sm:px-12">
        <Link
          href="/"
          aria-label={tCommon("back")}
          className="flex h-12 w-12 items-center justify-center rounded-full transition-transform active:scale-95"
          style={{
            color: COLORS.goldLight,
            background: "color-mix(in srgb, var(--am-gold-500) 10%, transparent)",
            border: "1px solid color-mix(in srgb, var(--am-gold-500) 35%, transparent)",
          }}
        >
          <ArrowLeft size={24} />
        </Link>
        <p
          className="mono text-[0.6875rem] uppercase tracking-[0.18em]"
          style={{ color: COLORS.goldLight }}
        >
          {t("eyebrow")}
        </p>
        <div className="w-12" aria-hidden />
      </header>

      {/* Main — single huge button, dead center */}
      <main className="flex flex-1 flex-col items-center justify-center px-6 sm:px-12">
        <StatusLine
          phase={phase}
          elapsed={elapsed}
          t={t}
          fortschritt={fortschrittText(fortschritt)}
        />

        {phase === "idle" || phase === "error" ? (
          <MicButton
            onClick={startRecording}
            ariaLabel={t("tapToStart")}
            kind="idle"
            // Nicht während erneut gesendet wird: sonst liefe die neue
            // Aufnahme, während die alte als „weitergegeben" zurückkommt.
            disabled={sendetErneut}
          />
        ) : phase === "requesting" ? (
          <MicButton ariaLabel={t("requestingMic")} kind="loading" />
        ) : phase === "recording" ? (
          <>
            <MicButton
              onClick={stopAndSave}
              ariaLabel={t("tapToStop")}
              kind="recording"
            />
            {/* Im Car-Mode ist der Pegelverlauf die einzige Rückmeldung,
                dass wirklich aufgenommen wird — hier gibt es weder
                Statuszeile noch Zeitanzeige im Blickfeld. */}
            <div className="mt-10 flex justify-center">
              <AufnahmeWelle stream={liveStream} hoehe={56} />
            </div>
          </>
        ) : phase === "saving" ? (
          <MicButton ariaLabel={t("saving")} kind="loading" />
        ) : phase === "saved" ? (
          <MicButton
            onClick={startRecording}
            ariaLabel={t("recordAnother")}
            kind="idle"
          />
        ) : phase === "denied" ? (
          <div className="mt-16 max-w-sm text-center">
            <p className="text-lg" style={{ color: "color-mix(in srgb, var(--am-blau-25) 80%, transparent)" }}>
              {t("deniedBody")}
            </p>
            <button
              type="button"
              onClick={startRecording}
              className="mt-8 rounded-full px-8 py-4 text-base font-medium transition-transform active:scale-95"
              style={{ background: COLORS.gold, color: COLORS.black }}
            >
              {tCommon("tryAgain")}
            </button>
          </div>
        ) : (
          <div className="mt-16 max-w-sm text-center">
            <p className="text-lg" style={{ color: "color-mix(in srgb, var(--am-blau-25) 80%, transparent)" }}>
              {t("unsupportedBody")}
            </p>
          </div>
        )}

        {error && (
          <p
            className="mt-10 max-w-sm text-center text-base"
            role="alert"
            style={{ color: COLORS.recording }}
          >
            {error}
          </p>
        )}

        {phase === "error" && gescheitert && (
          <div className="mt-6 flex max-w-sm flex-col items-center gap-3 text-center">
            <p className="text-sm" style={{ color: "color-mix(in srgb, var(--am-blau-25) 75%, transparent)" }}>
              {gescheitert.sicherung.gesichert
                ? tAufnahme("gesichert")
                : tAufnahme("nichtGesichert")}
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <button
                type="button"
                onClick={erneutSenden}
                disabled={sendetErneut}
                className="inline-flex min-h-[44px] items-center gap-2 rounded-full px-6 text-base font-medium transition-transform active:scale-95"
                style={{ background: COLORS.gold, color: COLORS.black }}
              >
                {sendetErneut && (
                  <Loader2 size={16} className="animate-spin" aria-hidden />
                )}
                {sendetErneut
                  ? (fortschrittText(fortschritt) ?? tAufnahme("sendet"))
                  : tAufnahme("erneutSenden")}
              </button>
              <button
                type="button"
                onClick={() =>
                  void alsDateiSpeichern(
                    gescheitert.sicherung.kopf,
                    gescheitert.ton,
                  ).catch(() => setError(tAufnahme("speichernFehler")))
                }
                disabled={sendetErneut}
                className="min-h-[44px] rounded-full px-6 text-base font-medium"
                style={{
                  color: COLORS.goldLight,
                  border: "1px solid color-mix(in srgb, var(--am-gold-500) 45%, transparent)",
                }}
              >
                {tAufnahme("alsDatei")}
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Fußzeile: „alles bleibt auf der Box“ nur, wenn die Messung es sagt
          (docs/DESIGN.md §5) — mit einem externen Ziel wäre der Satz falsch. */}
      {egress?.alles_bleibt && (
        <footer className="flex items-center justify-center gap-2 px-6 pb-[max(env(safe-area-inset-bottom),1.5rem)] pt-2 sm:px-12">
          <Lokal size={16} style={{ color: COLORS.goldLight, opacity: 0.8 }} aria-hidden />
          <p
            className="text-center text-xs"
            style={{ color: COLORS.goldLight, opacity: 0.6 }}
          >
            {t("footerHint")}
          </p>
        </footer>
      )}
    </div>
  );
}

function MicButton({
  onClick,
  ariaLabel,
  kind,
  disabled = false,
}: {
  onClick?: () => void;
  ariaLabel: string;
  kind: "idle" | "recording" | "loading";
  disabled?: boolean;
}) {
  const baseClasses =
    "immersive-in-delayed mt-12 flex h-44 w-44 items-center justify-center rounded-full transition-transform sm:h-56 sm:w-56";

  if (kind === "idle") {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={ariaLabel}
        disabled={disabled}
        className={`${baseClasses} active:scale-95 disabled:opacity-40`}
        style={{
          background: COLORS.gold,
          color: COLORS.black,
        }}
      >
        <Aufnahmezeichen zeichen={Mic} size={96} />
      </button>
    );
  }

  if (kind === "recording") {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={ariaLabel}
        aria-pressed
        className={`${baseClasses} active:scale-95`}
        style={{
          background: COLORS.goldDeep,
          color: COLORS.white,
          animation: "pulse-gold-strong 1.8s ease-in-out infinite",
        }}
      >
        <Aufnahmezeichen zeichen={Square} size={80} fill="currentColor" />
      </button>
    );
  }

  // loading (requesting / saving)
  return (
    <button
      type="button"
      disabled
      aria-label={ariaLabel}
      className={baseClasses}
      style={{
        background: "color-mix(in srgb, var(--am-gold-500) 18%, transparent)",
        color: COLORS.goldLight,
      }}
    >
      <Aufnahmezeichen zeichen={Loader2} size={96} className="animate-spin" />
    </button>
  );
}

function StatusLine({
  phase,
  elapsed,
  t,
  fortschritt,
}: {
  phase: Phase;
  elapsed: number;
  t: ReturnType<typeof useTranslations>;
  fortschritt: string | null;
}) {
  if (phase === "recording") {
    return (
      <div className="text-center">
        <p
          className="mono text-[0.6875rem] uppercase tracking-[0.18em]"
          style={{ color: COLORS.goldLight, opacity: 0.7 }}
        >
          {t("statusRecording")}
        </p>
        <p
          className="mono mt-4 text-7xl font-medium tabular-nums sm:text-8xl"
          aria-live="polite"
          style={{ color: COLORS.goldLight }}
        >
          {formatDuration(elapsed)}
        </p>
      </div>
    );
  }
  if (phase === "saving") {
    return (
      <div className="text-center">
        <p className="text-lg" style={{ color: "color-mix(in srgb, var(--am-blau-25) 75%, transparent)" }}>
          {t("statusSaving")}
        </p>
        {fortschritt && (
          <p
            className="mono mt-2 text-sm tabular-nums"
            aria-live="polite"
            style={{ color: COLORS.goldLight, opacity: 0.8 }}
          >
            {fortschritt}
          </p>
        )}
      </div>
    );
  }
  if (phase === "saved") {
    return (
      <div className="flex flex-col items-center text-center">
        <CheckCircle2 size={40} style={{ color: COLORS.goldLight }} />
        <p className="mt-4 text-2xl" style={{ color: COLORS.white }}>
          {t("statusSaved")}
        </p>
        <p
          className="mt-2 text-sm"
          style={{ color: COLORS.goldLight, opacity: 0.7 }}
        >
          {t("recordAnotherHint")}
        </p>
      </div>
    );
  }
  if (phase === "requesting") {
    return (
      <p
        className="text-center text-lg"
        style={{ color: "color-mix(in srgb, var(--am-blau-25) 75%, transparent)" }}
      >
        {t("requestingMic")}
      </p>
    );
  }
  // idle / error / denied / unsupported
  return (
    <div className="text-center">
      <p
        className="mono text-[0.6875rem] uppercase tracking-[0.18em]"
        style={{ color: COLORS.goldLight, opacity: 0.7 }}
      >
        {t("statusReady")}
      </p>
      <p
        className="mt-4 max-w-sm text-base"
        style={{ color: "color-mix(in srgb, var(--am-blau-25) 65%, transparent)" }}
      >
        {t("idleHint")}
      </p>
    </div>
  );
}
