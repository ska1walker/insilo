"use client";

import { CheckCircle2, Loader2, Mic, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { RecordingIndicator } from "@/components/recording-indicator";
import { ApiError } from "@/lib/api/client";
import { enrollSpeaker, type EnrollResult, type OrgSpeaker } from "@/lib/api/speakers";
import { formatDuration } from "@/lib/format";

const PREFERRED_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

const NORDWIND_TEXT = `Einst stritten sich Nordwind und Sonne, wer von ihnen beiden wohl der Stärkere wäre, als ein Wanderer, der in einen warmen Mantel gehüllt war, des Weges daherkam. Sie wurden einig, dass derjenige für den Stärkeren gelten sollte, der den Wanderer zwingen würde, seinen Mantel abzunehmen. Der Nordwind blies mit aller Macht, aber je mehr er blies, desto fester hüllte sich der Wanderer in seinen Mantel ein. Endlich gab der Nordwind den Kampf auf. Nun erwärmte die Sonne die Luft mit ihren freundlichen Strahlen, und schon nach wenigen Augenblicken zog der Wanderer seinen Mantel aus. Da musste der Nordwind zugeben, dass die Sonne von ihnen beiden der Stärkere war.`;

function pickMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  for (const t of PREFERRED_MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return null;
}

type Phase =
  | "intro"
  | "requesting"
  | "recording"
  | "uploading"
  | "success"
  | "error"
  | "denied"
  | "unsupported";

/**
 * Modal-Dialog zum Aufnehmen einer dedizierten Stimmprobe für einen
 * Org-Sprecher. Zeigt den phonetisch ausgewogenen Standardtext
 * „Der Nordwind und die Sonne" + Recorder + Upload-Feedback.
 *
 * Empfohlene Dauer: ~30–45 s (volle Vorlage). Backend fordert min. 5 s
 * Sprache nach Silero-VAD-Trim.
 */
export function VoiceEnrollmentDialog({
  speaker,
  onClose,
  onSuccess,
}: {
  speaker: OrgSpeaker;
  onClose: () => void;
  onSuccess: (result: EnrollResult) => void;
}) {
  const [phase, setPhase] = useState<Phase>("intro");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EnrollResult | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const tickRef = useRef<number | null>(null);
  const mimeRef = useRef<string>("audio/webm");

  useEffect(() => {
    return () => cleanup();
  }, []);

  function cleanup() {
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try {
        recorderRef.current.stop();
      } catch {
        /* ignore */
      }
    }
    recorderRef.current = null;
  }

  async function startRecording() {
    setError(null);
    const mime = pickMimeType();
    if (!mime) {
      setPhase("unsupported");
      return;
    }
    mimeRef.current = mime;
    setPhase("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream, { mimeType: mime });
      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      recorder.start(1000);
      recorderRef.current = recorder;
      startedAtRef.current = Date.now();
      setElapsed(0);
      tickRef.current = window.setInterval(() => {
        setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }, 500);
      setPhase("recording");
    } catch (err) {
      console.error("getUserMedia failed", err);
      setPhase("denied");
    }
  }

  async function stopRecording() {
    const recorder = recorderRef.current;
    if (!recorder) return;

    setPhase("uploading");
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }

    const blob: Blob = await new Promise((resolve) => {
      recorder.onstop = () => {
        const out = new Blob(chunksRef.current, { type: mimeRef.current });
        resolve(out);
      };
      recorder.stop();
    });

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    if (blob.size === 0) {
      setError("Die Aufnahme war leer. Bitte erneut versuchen.");
      setPhase("error");
      return;
    }

    try {
      const r = await enrollSpeaker(speaker.id, blob, mimeRef.current);
      setResult(r);
      setPhase("success");
      onSuccess(r);
    } catch (err) {
      console.error("enroll failed", err);
      if (err instanceof ApiError && err.status === 422) {
        setError(
          (err.body as { detail?: string } | null)?.detail ??
            "Zu wenig erkennbare Sprache. Bitte erneut versuchen.",
        );
      } else if (err instanceof ApiError) {
        setError(
          `Fehler ${err.status}: ${
            (err.body as { detail?: string } | null)?.detail ?? "Upload abgelehnt"
          }`,
        );
      } else {
        setError("Upload fehlgeschlagen — Verbindung prüfen.");
      }
      setPhase("error");
    }
  }

  function handleRetry() {
    setError(null);
    setResult(null);
    setPhase("intro");
    setElapsed(0);
  }

  function handleClose() {
    cleanup();
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal
      aria-label="Stimmprobe aufnehmen"
    >
      {phase === "recording" && <RecordingIndicator />}

      <div className="relative max-h-[90vh] w-full max-w-[640px] overflow-y-auto rounded-lg border border-border-subtle bg-white p-6 shadow-2xl">
        <button
          type="button"
          onClick={handleClose}
          className="absolute right-4 top-4 rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
          aria-label="Schließen"
        >
          <X className="h-4 w-4" strokeWidth={1.75} />
        </button>

        <h2 className="font-display text-2xl font-medium tracking-tight">
          Stimmprobe für{" "}
          <span style={{ color: "var(--gold-deep)" }}>{speaker.display_name}</span>
        </h2>
        <p className="mt-2 text-sm text-text-secondary">
          Lesen Sie den folgenden Standardtext laut und deutlich vor. Er
          dauert etwa 35–45 Sekunden und enthält alle wichtigen deutschen
          Laute — damit lernt Insilo die Stimme besonders genau.
        </p>

        {(phase === "intro" || phase === "requesting" || phase === "denied" || phase === "unsupported") && (
          <div className="mt-5 rounded-md border border-border-subtle bg-surface-soft p-4 text-sm leading-relaxed text-text-primary">
            <p className="mono mb-2 text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
              Der Nordwind und die Sonne
            </p>
            <p>{NORDWIND_TEXT}</p>
          </div>
        )}

        {phase === "recording" && (
          <div className="mt-5 rounded-md border bg-surface-soft p-4 text-sm leading-relaxed text-text-primary"
            style={{ borderColor: "var(--gold)" }}
          >
            <div className="mb-3 flex items-center justify-between">
              <p
                className="mono text-[0.6875rem] uppercase tracking-[0.08em]"
                style={{ color: "var(--gold-deep)" }}
              >
                Aufnahme läuft
              </p>
              <p className="mono tabular-nums text-base font-medium" aria-live="polite">
                {formatDuration(elapsed * 1000)}
              </p>
            </div>
            <p>{NORDWIND_TEXT}</p>
          </div>
        )}

        {phase === "uploading" && (
          <div className="mt-5 flex items-center gap-3 rounded-md bg-surface-soft p-4 text-sm text-text-secondary">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
            Stimmprobe wird verarbeitet …
          </div>
        )}

        {phase === "success" && result && (
          <div
            className="mt-5 rounded-md border p-4 text-sm"
            style={{
              borderColor: "var(--success)",
              background: "rgba(74,124,89,0.06)",
              color: "var(--success)",
            }}
          >
            <div className="flex items-center gap-2 font-medium">
              <CheckCircle2 className="h-4 w-4" strokeWidth={1.75} />
              Stimmprobe gespeichert
            </div>
            <p className="mt-1 text-xs opacity-90">
              {result.voiced_seconds.toFixed(1)} s erkennbare Sprache aus{" "}
              {result.total_seconds.toFixed(1)} s Aufnahme · Sprecher hat
              jetzt {result.sample_count}{" "}
              {result.sample_count === 1 ? "Stimmprobe" : "Stimmproben"}.
            </p>
          </div>
        )}

        {phase === "error" && error && (
          <div
            className="mt-5 rounded-md border p-4 text-sm"
            style={{
              borderColor: "var(--error)",
              background: "rgba(163,58,47,0.06)",
              color: "var(--error)",
            }}
          >
            <p className="font-medium">Aufnahme nicht verwertbar</p>
            <p className="mt-1 text-xs opacity-90">{error}</p>
          </div>
        )}

        {phase === "denied" && (
          <div
            className="mt-5 rounded-md border p-4 text-sm"
            style={{
              borderColor: "var(--error)",
              background: "rgba(163,58,47,0.06)",
              color: "var(--error)",
            }}
          >
            <p className="font-medium">Mikrofonzugriff verweigert</p>
            <p className="mt-1 text-xs opacity-90">
              Bitte erlauben Sie Insilo den Zugriff aufs Mikrofon in den
              Browser-Einstellungen und versuchen Sie es erneut.
            </p>
          </div>
        )}

        {phase === "unsupported" && (
          <div
            className="mt-5 rounded-md border p-4 text-sm"
            style={{
              borderColor: "var(--error)",
              background: "rgba(163,58,47,0.06)",
              color: "var(--error)",
            }}
          >
            <p className="font-medium">Browser unterstützt keine Aufnahme</p>
            <p className="mt-1 text-xs opacity-90">
              Bitte nutzen Sie einen aktuellen Chrome- oder Safari-Browser.
            </p>
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-text-meta">
            Die Aufnahme verlässt Ihre Olares-Box nicht.
          </p>
          <div className="flex gap-2">
            {phase === "intro" && (
              <>
                <button type="button" onClick={handleClose} className="btn-tertiary">
                  Abbrechen
                </button>
                <button
                  type="button"
                  onClick={startRecording}
                  className="btn-primary inline-flex items-center gap-2"
                >
                  <Mic className="h-4 w-4" strokeWidth={1.75} />
                  Aufnahme starten
                </button>
              </>
            )}
            {phase === "requesting" && (
              <button type="button" disabled className="btn-primary">
                Mikrofon wird angefragt …
              </button>
            )}
            {phase === "recording" && (
              <button
                type="button"
                onClick={stopRecording}
                className="btn-primary inline-flex items-center gap-2"
                style={{ background: "var(--gold-deep)" }}
              >
                <Square className="h-4 w-4 fill-current" strokeWidth={1.75} />
                Stopp & speichern
              </button>
            )}
            {phase === "uploading" && (
              <button type="button" disabled className="btn-primary">
                Wird verarbeitet …
              </button>
            )}
            {(phase === "error" || phase === "denied") && (
              <>
                <button type="button" onClick={handleClose} className="btn-tertiary">
                  Schließen
                </button>
                <button type="button" onClick={handleRetry} className="btn-primary">
                  Erneut versuchen
                </button>
              </>
            )}
            {phase === "success" && (
              <button type="button" onClick={handleClose} className="btn-primary">
                Fertig
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
