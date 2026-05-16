"use client";

import { ArrowLeft, CheckCircle2, Loader2, Mic, Square } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { createMeeting } from "@/lib/api/meetings";
import { ASR_AUDIO_CONSTRAINTS, ASR_RECORDER_OPTIONS } from "@/lib/audio";
import { defaultMeetingTitle, formatDuration } from "@/lib/format";
import { useLocale } from "next-intl";

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

/**
 * Schauerfunktion — Car-Mode-Aufnahme für unterwegs (auto, walking, shower).
 *
 * UX-Ziel: Spotify Car-Mode. Dunkler Vollbild-BG, ein einziger Riesen-Button
 * mittig, sonst nur die nötigsten Statuszeilen. State-Maschine:
 *   idle → recording → saving → saved (5 s Auto-Reset) → idle
 *
 * Kein Template-Picker, keine Sprach-Auswahl, kein Save-Button. Aufnahme
 * landet als `quick_mode=true` im Backend, das Backend setzt das
 * Schnellnotiz-Template (00000005) automatisch und forciert die
 * Webhook-Auto-Dispatch (siehe notify.py).
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

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0A0A0A] text-white">
      {/* Top bar — minimal, just a back-arrow */}
      <header className="flex items-center justify-between px-6 pt-[max(env(safe-area-inset-top),1.5rem)] pb-2 sm:px-12">
        <Link
          href="/"
          aria-label={tCommon("back")}
          className="flex h-12 w-12 items-center justify-center rounded-full text-white/70 transition-colors hover:bg-white/5 hover:text-white"
        >
          <ArrowLeft className="h-6 w-6" strokeWidth={1.5} />
        </Link>
        <p className="mono text-[0.6875rem] uppercase tracking-[0.12em] text-white/40">
          {t("eyebrow")}
        </p>
        <div className="w-12" aria-hidden />
      </header>

      {/* Main — single huge button, dead center */}
      <main className="flex flex-1 flex-col items-center justify-center px-6 sm:px-12">
        <StatusLine phase={phase} elapsed={elapsed} t={t} />

        {phase === "idle" || phase === "error" ? (
          <button
            type="button"
            onClick={startRecording}
            aria-label={t("tapToStart")}
            className="mt-12 flex h-44 w-44 items-center justify-center rounded-full bg-white text-black shadow-[0_0_60px_rgba(255,255,255,0.15)] transition-transform active:scale-95 sm:h-56 sm:w-56"
          >
            <Mic className="h-20 w-20 sm:h-24 sm:w-24" strokeWidth={1.5} />
          </button>
        ) : phase === "requesting" ? (
          <button
            type="button"
            disabled
            aria-label={t("requestingMic")}
            className="mt-12 flex h-44 w-44 items-center justify-center rounded-full bg-white/20 text-white sm:h-56 sm:w-56"
          >
            <Loader2 className="h-20 w-20 animate-spin sm:h-24 sm:w-24" strokeWidth={1.5} />
          </button>
        ) : phase === "recording" ? (
          <button
            type="button"
            onClick={stopAndSave}
            aria-label={t("tapToStop")}
            className="mt-12 flex h-44 w-44 items-center justify-center rounded-full bg-recording text-white shadow-[0_0_80px_rgba(220,38,38,0.45)] transition-transform active:scale-95 sm:h-56 sm:w-56"
            style={{ animation: "pulse-quick 1.6s ease-in-out infinite" }}
          >
            <Square className="h-16 w-16 sm:h-20 sm:w-20" strokeWidth={0} fill="currentColor" />
          </button>
        ) : phase === "saving" ? (
          <button
            type="button"
            disabled
            aria-label={t("saving")}
            className="mt-12 flex h-44 w-44 items-center justify-center rounded-full bg-white/20 text-white sm:h-56 sm:w-56"
          >
            <Loader2 className="h-20 w-20 animate-spin sm:h-24 sm:w-24" strokeWidth={1.5} />
          </button>
        ) : phase === "saved" ? (
          <button
            type="button"
            onClick={startRecording}
            aria-label={t("recordAnother")}
            className="mt-12 flex h-44 w-44 items-center justify-center rounded-full bg-white text-black shadow-[0_0_60px_rgba(255,255,255,0.15)] transition-transform active:scale-95 sm:h-56 sm:w-56"
          >
            <Mic className="h-20 w-20 sm:h-24 sm:w-24" strokeWidth={1.5} />
          </button>
        ) : phase === "denied" ? (
          <div className="mt-12 max-w-sm text-center">
            <p className="text-lg text-white/80">{t("deniedBody")}</p>
            <button
              type="button"
              onClick={startRecording}
              className="mt-8 rounded-full bg-white px-8 py-4 text-base font-medium text-black"
            >
              {tCommon("tryAgain")}
            </button>
          </div>
        ) : (
          <div className="mt-12 max-w-sm text-center">
            <p className="text-lg text-white/80">{t("unsupportedBody")}</p>
          </div>
        )}

        {error && (
          <p className="mt-10 max-w-sm text-center text-base text-recording" role="alert">
            {error}
          </p>
        )}
      </main>

      {/* Bottom — tagline + version of friendly help text */}
      <footer className="px-6 pb-[max(env(safe-area-inset-bottom),1.5rem)] pt-2 sm:px-12">
        <p className="text-center text-sm text-white/40">{t("footerHint")}</p>
      </footer>

      <style jsx>{`
        @keyframes pulse-quick {
          0%, 100% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.04);
          }
        }
      `}</style>
    </div>
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
        <p className="mono text-[0.6875rem] uppercase tracking-[0.12em] text-recording">
          {t("statusRecording")}
        </p>
        <p
          className="mono mt-3 text-5xl font-medium tabular-nums sm:text-6xl"
          aria-live="polite"
        >
          {formatDuration(elapsed)}
        </p>
      </div>
    );
  }
  if (phase === "saving") {
    return (
      <p className="text-center text-lg text-white/70">{t("statusSaving")}</p>
    );
  }
  if (phase === "saved") {
    return (
      <div className="flex flex-col items-center text-center">
        <CheckCircle2 className="h-10 w-10 text-emerald-400" strokeWidth={1.5} />
        <p className="mt-3 text-xl text-white">{t("statusSaved")}</p>
        <p className="mt-2 text-sm text-white/50">{t("recordAnotherHint")}</p>
      </div>
    );
  }
  if (phase === "requesting") {
    return (
      <p className="text-center text-lg text-white/70">{t("requestingMic")}</p>
    );
  }
  // idle / error / denied / unsupported
  return (
    <div className="text-center">
      <p className="mono text-[0.6875rem] uppercase tracking-[0.12em] text-white/40">
        {t("statusReady")}
      </p>
      <p className="mt-3 max-w-sm text-base text-white/60">{t("idleHint")}</p>
    </div>
  );
}
