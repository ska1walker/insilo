"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { RecordingIndicator } from "@/components/recording-indicator";
import { ApiError } from "@/lib/api/client";
import { createMeeting } from "@/lib/api/meetings";
import { listTemplates, type TemplateDto } from "@/lib/api/templates";
import { defaultMeetingTitle, formatDuration } from "@/lib/format";

const DEFAULT_TEMPLATE_ID = "00000000-0000-0000-0000-000000000001";

type Phase = "idle" | "requesting" | "recording" | "saving" | "denied" | "unsupported";

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

export default function AufnahmePage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const tickRef = useRef<number | null>(null);

  const [templates, setTemplates] = useState<TemplateDto[] | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string>(DEFAULT_TEMPLATE_ID);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]));   // backend down → just disable picker
  }, []);

  useEffect(() => {
    return () => stopTracksAndTick();
  }, []);

  function stopTracksAndTick() {
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }

  async function startRecording() {
    setError(null);
    const mime = pickMimeType();
    if (!mime) {
      setPhase("unsupported");
      return;
    }
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
      setPhase("recording");
      tickRef.current = window.setInterval(() => {
        setElapsed(Date.now() - startedAtRef.current);
      }, 250);
    } catch (err) {
      console.error("getUserMedia failed", err);
      const name = (err as DOMException)?.name;
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setPhase("denied");
      } else {
        setPhase("idle");
        setError("Das Mikrofon konnte nicht gestartet werden. Bitte prüfen Sie die Browser-Berechtigungen.");
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

    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      recorder.stop();
    });

    stopTracksAndTick();

    const mimeType = recorder.mimeType || "audio/webm";
    const blob = new Blob(chunksRef.current, { type: mimeType });
    const now = Date.now();
    const title = defaultMeetingTitle(now);

    try {
      const meeting = await createMeeting({
        blob,
        title,
        durationMs,
        mimeType,
        templateId: selectedTemplate,
      });
      router.push(`/m/${meeting.id}`);
    } catch (err) {
      console.error("upload failed", err);
      setPhase("idle");
      if (err instanceof ApiError) {
        setError(`Upload fehlgeschlagen (HTTP ${err.status}). Backend erreichbar?`);
      } else {
        setError("Upload fehlgeschlagen. Bitte erneut versuchen.");
      }
    }
  }

  function cancel() {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = null;
      try { recorder.stop(); } catch {/* ignore */}
    }
    chunksRef.current = [];
    stopTracksAndTick();
    setPhase("idle");
    setElapsed(0);
    router.push("/");
  }

  return (
    <>
      {phase === "recording" && <RecordingIndicator />}

      <main className="mx-auto flex min-h-[calc(100dvh-72px)] max-w-[640px] flex-col items-center justify-center px-6 py-16 md:px-12">
        <div className="w-full text-center">
          <p className="mono mb-4 text-xs uppercase tracking-[0.08em] text-text-meta">
            {phaseLabel(phase)}
          </p>

          <p
            className="mono mb-12 text-6xl font-medium tabular-nums"
            aria-live="polite"
          >
            {formatDuration(phase === "recording" || phase === "saving" ? elapsed : 0)}
          </p>

          {phase === "idle" && (
            <button type="button" className="btn-record" onClick={startRecording}>
              Start
            </button>
          )}

          {phase === "requesting" && (
            <button type="button" className="btn-record" disabled>…</button>
          )}

          {phase === "recording" && (
            <button
              type="button"
              className="btn-record recording"
              onClick={stopAndSave}
              aria-pressed
            >
              Stopp
            </button>
          )}

          {phase === "saving" && (
            <button type="button" className="btn-record recording" disabled>…</button>
          )}

          {(phase === "idle" || phase === "recording") && (
            <div className="mt-12">
              <button type="button" onClick={cancel} className="btn-tertiary">
                Abbrechen
              </button>
            </div>
          )}

          {phase === "idle" && templates && templates.length > 0 && (
            <div className="mt-16 text-left">
              <p className="mb-3 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
                Vorlage für die Zusammenfassung
              </p>
              <div className="rounded-lg border border-border-subtle bg-white">
                {templates.map((t, i) => (
                  <label
                    key={t.id}
                    className={`flex cursor-pointer items-start gap-3 p-4 ${
                      i > 0 ? "border-t border-border-subtle" : ""
                    } ${selectedTemplate === t.id ? "bg-gold-faint" : ""}`}
                  >
                    <input
                      type="radio"
                      name="template"
                      value={t.id}
                      checked={selectedTemplate === t.id}
                      onChange={(e) => setSelectedTemplate(e.target.value)}
                      className="mt-1 accent-black"
                    />
                    <div className="min-w-0">
                      <p className="font-medium text-text-primary">{t.name}</p>
                      {t.description && (
                        <p className="mt-1 text-sm text-text-secondary">
                          {t.description}
                        </p>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {phase === "denied" && (
            <Notice
              title="Mikrofon-Zugriff verweigert"
              body="Bitte erlauben Sie insilo den Zugriff auf Ihr Mikrofon in den Browser-Einstellungen und versuchen Sie es erneut."
              actionLabel="Erneut versuchen"
              onAction={() => { setPhase("idle"); startRecording(); }}
            />
          )}

          {phase === "unsupported" && (
            <Notice
              title="Browser unterstützt keine Audio-Aufnahme"
              body="Dieser Browser kann keine Audio-Aufnahmen erstellen. Bitte verwenden Sie eine aktuelle Version von Chrome, Firefox, Safari oder Edge."
            />
          )}

          {error && (
            <p className="mt-8 text-sm text-recording" role="alert">{error}</p>
          )}

          <p className="mt-16 max-w-[420px] text-center text-sm text-text-meta">
            Audio bleibt auf Ihrer Olares-Box. Kein Cloud-Upload, keine Drittanbieter.
          </p>
        </div>
      </main>
    </>
  );
}

function phaseLabel(p: Phase): string {
  switch (p) {
    case "idle": return "Bereit";
    case "requesting": return "Mikrofon wird angefragt";
    case "recording": return "● Aufnahme läuft";
    case "saving": return "Übertragen";
    case "denied": return "Zugriff verweigert";
    case "unsupported": return "Nicht unterstützt";
  }
}

function Notice({
  title, body, actionLabel, onAction,
}: {
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="mt-8 rounded-lg border border-border-subtle bg-white p-6 text-left">
      <p className="font-display text-lg font-medium">{title}</p>
      <p className="mt-2 text-sm text-text-secondary">{body}</p>
      {actionLabel && onAction && (
        <button type="button" onClick={onAction} className="btn-secondary mt-4">
          {actionLabel}
        </button>
      )}
    </div>
  );
}
