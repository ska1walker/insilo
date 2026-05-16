"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Mic,
  ShieldCheck,
  Square,
} from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { createMeeting } from "@/lib/api/meetings";
import { ASR_AUDIO_CONSTRAINTS, ASR_RECORDER_OPTIONS } from "@/lib/audio";
import { defaultMeetingTitle, formatDuration } from "@/lib/format";

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

// Insilo brand tokens for the dark Car-Mode palette. Direct hex values
// (not CSS vars) because inline style + var() showed parse issues in
// some browser/build combinations — caused the BG to render white in
// v0.1.53/.54. Hex bypasses any var-resolution path.
const COLORS = {
  black: "#0A0A0A",
  white: "#ffffff",
  gold: "#C9A961",
  goldLight: "#E6D4A3",
  goldDeep: "#9C8147",
  recording: "#C84A3F",
} as const;

// Gradient als Image-Layer; backgroundColor wird separat als Insilo-Black
// gesetzt. Sicherer als Multi-Layer-`background`-Shorthand mit CSS-vars als
// background-color (Browser-Parser handhabt das uneinheitlich).
const BG_GRADIENT_IDLE_IMG =
  "radial-gradient(circle at 50% 42%, rgba(201, 169, 97, 0.10) 0%, transparent 55%)";
const BG_GRADIENT_ACTIVE_IMG =
  "radial-gradient(circle at 50% 42%, rgba(201, 169, 97, 0.22) 0%, transparent 60%)";

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
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const tickRef = useRef<number | null>(null);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);
  const savedResetRef = useRef<number | null>(null);

  // Dark-Mode-Transition: body-class steuert globalen Fade. globals.css
  // versteckt zusätzlich den normalen Insilo-Header während aktiv.
  useEffect(() => {
    document.body.classList.add("quick-capture-active");
    return () => document.body.classList.remove("quick-capture-active");
  }, []);

  // Cleanup all browser resources on unmount.
  useEffect(() => {
    return () => {
      stopTracksAndTick();
      releaseWakeLock();
      if (savedResetRef.current !== null) {
        window.clearTimeout(savedResetRef.current);
      }
    };
  }, []);

  function stopTracksAndTick() {
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
    }
  }

  async function requestWakeLock() {
    if (!("wakeLock" in navigator)) return;
    try {
      // Cast: WakeLockSentinel typing is still gated on lib.dom updates
      // in older TS targets; the runtime API is widely shipped (iOS 16.4+,
      // Chrome 84+).
      wakeLockRef.current = await (
        navigator as unknown as {
          wakeLock: { request(t: "screen"): Promise<WakeLockSentinel> };
        }
      ).wakeLock.request("screen");
    } catch {
      /* user-rejected or unsupported; aufnahme läuft trotzdem */
    }
  }

  async function releaseWakeLock() {
    if (wakeLockRef.current) {
      try {
        await wakeLockRef.current.release();
      } catch {
        /* ignore */
      }
      wakeLockRef.current = null;
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
    setPhase("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: ASR_AUDIO_CONSTRAINTS,
      });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream, {
        mimeType: mime,
        ...ASR_RECORDER_OPTIONS,
      });
      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      recorder.start(1000);
      recorderRef.current = recorder;
      startedAtRef.current = Date.now();
      setElapsed(0);
      setPhase("recording");
      vibrate(50);
      requestWakeLock();
      tickRef.current = window.setInterval(() => {
        setElapsed(Date.now() - startedAtRef.current);
      }, 250);
    } catch (err) {
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
    releaseWakeLock();

    const mimeType = recorder.mimeType || "audio/webm";
    const blob = new Blob(chunksRef.current, { type: mimeType });
    const now = Date.now();
    const title = defaultMeetingTitle(now, locale, t("defaultTitlePrefix"));

    try {
      await createMeeting({
        blob,
        title,
        durationMs,
        mimeType,
        quickMode: true,
      });
      setPhase("saved");
      savedResetRef.current = window.setTimeout(() => {
        setPhase("idle");
        setElapsed(0);
        savedResetRef.current = null;
      }, SAVED_AUTO_RESET_MS);
    } catch (err) {
      setPhase("error");
      if (err instanceof ApiError) {
        setError(t("uploadFailedHttp", { status: err.status }));
      } else {
        setError(t("uploadFailedTryAgain"));
      }
    }
  }

  const isActive = phase === "recording" || phase === "saving";
  const bgStyle = {
    backgroundColor: COLORS.black,
    backgroundImage: isActive ? BG_GRADIENT_ACTIVE_IMG : BG_GRADIENT_IDLE_IMG,
    color: COLORS.white,
    transition: "background-image 600ms var(--ease-out)",
  };

  return (
    <div
      // .quick-capture-shell in globals.css setzt background-color via
      // !important — Tailwind-Class und inline-style haben in v0.1.53-55
      // trotz korrektem Bundle nicht durchgesetzt. Diese Klasse ist
      // idiot-proof. Inline-style enthält weiterhin den Gradient-Overlay.
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
            background: "rgba(201, 169, 97, 0.10)",
            border: "1px solid rgba(201, 169, 97, 0.35)",
          }}
        >
          <ArrowLeft className="h-6 w-6" strokeWidth={1.5} />
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
        <StatusLine phase={phase} elapsed={elapsed} t={t} />

        {phase === "idle" || phase === "error" ? (
          <MicButton
            onClick={startRecording}
            ariaLabel={t("tapToStart")}
            kind="idle"
          />
        ) : phase === "requesting" ? (
          <MicButton ariaLabel={t("requestingMic")} kind="loading" />
        ) : phase === "recording" ? (
          <MicButton
            onClick={stopAndSave}
            ariaLabel={t("tapToStop")}
            kind="recording"
          />
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
            <p className="text-lg" style={{ color: "rgba(255,255,255,0.8)" }}>
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
            <p className="text-lg" style={{ color: "rgba(255,255,255,0.8)" }}>
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
      </main>

      {/* Bottom — trust hint with ShieldCheck */}
      <footer className="flex items-center justify-center gap-2 px-6 pb-[max(env(safe-area-inset-bottom),1.5rem)] pt-2 sm:px-12">
        <ShieldCheck
          className="h-3.5 w-3.5 shrink-0"
          strokeWidth={1.75}
          style={{ color: COLORS.goldDeep, opacity: 0.8 }}
          aria-hidden
        />
        <p
          className="text-center text-xs"
          style={{ color: COLORS.goldLight, opacity: 0.6 }}
        >
          {t("footerHint")}
        </p>
      </footer>
    </div>
  );
}

function MicButton({
  onClick,
  ariaLabel,
  kind,
}: {
  onClick?: () => void;
  ariaLabel: string;
  kind: "idle" | "recording" | "loading";
}) {
  const baseClasses =
    "immersive-in-delayed mt-12 flex h-44 w-44 items-center justify-center rounded-full transition-transform sm:h-56 sm:w-56";

  if (kind === "idle") {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={ariaLabel}
        className={`${baseClasses} active:scale-95`}
        style={{
          background: COLORS.gold,
          color: COLORS.black,
          boxShadow:
            "0 0 0 1px rgba(201, 169, 97, 0.45), 0 0 80px rgba(201, 169, 97, 0.25)",
        }}
      >
        <Mic className="h-24 w-24 sm:h-28 sm:w-28" strokeWidth={1.5} />
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
        <Square
          className="h-20 w-20 sm:h-24 sm:w-24"
          strokeWidth={0}
          fill="currentColor"
        />
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
        background: "rgba(201, 169, 97, 0.18)",
        color: COLORS.goldLight,
      }}
    >
      <Loader2
        className="h-24 w-24 animate-spin sm:h-28 sm:w-28"
        strokeWidth={1.5}
      />
    </button>
  );
}

function StatusLine({
  phase,
  elapsed,
  t,
}: {
  phase: Phase;
  elapsed: number;
  t: ReturnType<typeof useTranslations>;
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
      <p
        className="text-center text-lg"
        style={{ color: "rgba(255,255,255,0.75)" }}
      >
        {t("statusSaving")}
      </p>
    );
  }
  if (phase === "saved") {
    return (
      <div className="flex flex-col items-center text-center">
        <CheckCircle2
          className="h-12 w-12"
          strokeWidth={1.5}
          style={{ color: COLORS.goldLight }}
        />
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
        style={{ color: "rgba(255,255,255,0.75)" }}
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
        style={{ color: "rgba(255,255,255,0.65)" }}
      >
        {t("idleHint")}
      </p>
    </div>
  );
}
