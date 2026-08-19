"use client";

import { Loader2, Mic, ShieldAlert, ShieldCheck, Square } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { AufnahmeWelle } from "@/components/aufnahme-welle";
import { RecordingIndicator } from "@/components/recording-indicator";
import { ApiError } from "@/lib/api/client";
import { useEgress } from "@/lib/api/egress";
import { createMeeting } from "@/lib/api/meetings";
import { listTemplates, type TemplateDto } from "@/lib/api/templates";
import { ASR_AUDIO_CONSTRAINTS, ASR_RECORDER_OPTIONS } from "@/lib/audio";
import { defaultMeetingTitle, formatDuration } from "@/lib/format";

const DEFAULT_TEMPLATE_ID = "00000000-0000-0000-0000-000000000001";

const AUDIO_LANGUAGE_OPTIONS = ["auto", "de", "en", "fr", "es", "it"] as const;
type AudioLanguage = (typeof AUDIO_LANGUAGE_OPTIONS)[number];

type Phase =
  | "idle"
  | "requesting"
  | "recording"
  | "saving"
  | "denied"
  | "unsupported";

type Variant = "full" | "compact";

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

/**
 * Self-contained recording block — captures audio, picks a template,
 * uploads to the backend and redirects to /m/<id> on success.
 *
 * `variant="full"`     — vertikal zentriert, großer Timer (für /aufnahme)
 * `variant="compact"`  — eingebettet in Page-Flow (für /)
 */
export function RecordingBlock({ variant = "compact" }: { variant?: Variant }) {
  const router = useRouter();
  const t = useTranslations("recording");
  const tCommon = useTranslations("common");
  const tLocale = useTranslations("locale");
  const locale = useLocale();
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Die Welle braucht den Stream als State: ein Ref löst kein Rendern aus.
  const [liveStream, setLiveStream] = useState<MediaStream | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const tickRef = useRef<number | null>(null);

  const [templates, setTemplates] = useState<TemplateDto[] | null>(null);
  const [selectedTemplate, setSelectedTemplate] =
    useState<string>(DEFAULT_TEMPLATE_ID);
  const [audioLanguage, setAudioLanguage] = useState<AudioLanguage>("auto");

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]));
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
    setLiveStream(null);
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

    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      recorder.stop();
    });

    stopTracksAndTick();

    const mimeType = recorder.mimeType || "audio/webm";
    const blob = new Blob(chunksRef.current, { type: mimeType });
    const now = Date.now();
    const title = defaultMeetingTitle(now, locale, t("defaultTitlePrefix"));

    try {
      const meeting = await createMeeting({
        blob,
        title,
        durationMs,
        mimeType,
        templateId: selectedTemplate,
        audioLanguage,
      });
      router.push(`/m/${meeting.id}`);
    } catch (err) {
      console.error("upload failed", err);
      setPhase("idle");
      if (err instanceof ApiError) {
        setError(t("uploadFailedHttp", { status: err.status }));
      } else {
        setError(t("uploadFailedTryAgain"));
      }
    }
  }

  function cancel() {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = null;
      try {
        recorder.stop();
      } catch {
        /* ignore */
      }
    }
    chunksRef.current = [];
    stopTracksAndTick();
    setPhase("idle");
    setElapsed(0);
    if (variant === "full") router.push("/");
  }

  const isFull = variant === "full";
  const timerSize = isFull ? "text-6xl" : "text-5xl";
  const showTrustBadge = isFull;
  const cancelGoesHome = isFull;

  return (
    <>
      {phase === "recording" && <RecordingIndicator />}

      <div className="w-full text-center">
        <StatusEyebrow phase={phase} />

        {(phase === "recording" || phase === "saving") && (
          <p
            className={`mono mt-3 ${timerSize} font-medium tabular-nums text-text-primaer`}
            aria-live="polite"
          >
            {formatDuration(elapsed)}
          </p>
        )}

        {/* Der Pegelverlauf sitzt zwischen Zeit und Knopf: erst was läuft,
            dann ob Signal ankommt, dann die Handlung. */}
        {phase === "recording" && (
          <div className="mt-4 mb-10 flex justify-center">
            <AufnahmeWelle stream={liveStream} hoehe={isFull ? 48 : 36} />
          </div>
        )}

        {phase === "saving" && <div className="mb-10" />}

        {phase === "idle" && (
          <p
            className={`mono mt-3 mb-10 ${timerSize} font-medium tabular-nums text-text-deaktiviert`}
            aria-hidden
          >
            00:00
          </p>
        )}

        {phase === "idle" && (
          <button
            type="button"
            className="btn-record"
            onClick={startRecording}
            aria-label={t("start")}
          >
            <Mic className="btn-record-icon" strokeWidth={1.5} />
          </button>
        )}

        {phase === "requesting" && (
          <button
            type="button"
            className="btn-record"
            disabled
            aria-label={t("requestingMic")}
          >
            <Loader2
              className="btn-record-icon animate-spin"
              strokeWidth={1.5}
            />
          </button>
        )}

        {phase === "recording" && (
          <button
            type="button"
            className="btn-record recording"
            onClick={stopAndSave}
            aria-pressed
            aria-label={t("stop")}
          >
            <Square
              className="btn-record-icon"
              strokeWidth={0}
              fill="currentColor"
            />
          </button>
        )}

        {phase === "saving" && (
          <button
            type="button"
            className="btn-record recording"
            disabled
            aria-label={t("saving")}
          >
            <Loader2
              className="btn-record-icon animate-spin"
              strokeWidth={1.5}
            />
          </button>
        )}

        {phase === "idle" && (
          <p className="mt-5 text-sm text-text-gedaempft">{t("phaseIdle")}</p>
        )}

        {(phase === "idle" || phase === "recording") && cancelGoesHome && (
          <div className="mt-10">
            <button type="button" onClick={cancel} className="btn btn-still">
              {tCommon("cancel")}
            </button>
          </div>
        )}

        {phase === "idle" && templates && templates.length > 0 && (
          <div className={`${isFull ? "mt-16" : "mt-12"} text-left`}>
            <p className="mb-3 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-gedaempft">
              {t("templateLabel")}
            </p>
            <div className="rounded-lg border border-trennlinie bg-seite">
              {templates.map((t, i) => (
                <label
                  key={t.id}
                  className={`flex cursor-pointer items-start gap-3 p-4 ${
                    i > 0 ? "border-t border-trennlinie" : ""
                  } ${selectedTemplate === t.id ? "flaeche-auswahl" : ""}`}
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
                    <p className="font-medium text-text-primaer">{t.name}</p>
                    {t.description && (
                      <p className="mt-1 text-sm text-text-sekundaer">
                        {t.description}
                      </p>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {phase === "idle" && (
          <div className="mt-8 text-left">
            <label
              htmlFor="audio-language"
              className="mb-3 block text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-gedaempft"
            >
              {t("audioLanguageLabel")}
            </label>
            <select
              id="audio-language"
              value={audioLanguage}
              onChange={(e) => setAudioLanguage(e.target.value as AudioLanguage)}
              // pr-12 hält rechts Platz für das Auswahlzeichen frei, damit
              // lange Einträge nicht darunter laufen.
              className="w-full rounded-lg border border-trennlinie bg-seite py-3 pl-4 pr-12 text-text-primaer focus:border-rand-betont focus:outline-none"
            >
              {AUDIO_LANGUAGE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt === "auto"
                    ? t("audioLanguageAuto")
                    : tLocale(`names.${opt}` as "names.de")}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-text-gedaempft">
              {t("audioLanguageHint")}
            </p>
          </div>
        )}

        {phase === "denied" && (
          <Notice
            title={t("phaseDenied")}
            body={t("phaseDeniedHint")}
            actionLabel={tCommon("tryAgain")}
            onAction={() => {
              setPhase("idle");
              startRecording();
            }}
          />
        )}

        {phase === "unsupported" && (
          <Notice
            title={t("phaseUnsupported")}
            body={t("phaseUnsupportedHint")}
          />
        )}

        {error && (
          <p className="mt-8 text-sm text-fehler" role="alert">
            {error}
          </p>
        )}

        {showTrustBadge && <Datensouveraenitaet />}
      </div>
    </>
  );
}

function StatusEyebrow({ phase }: { phase: Phase }) {
  const t = useTranslations("recording");
  const label =
    phase === "idle"
      ? t("statusReady")
      : phase === "requesting"
        ? t("requestingMic")
        : phase === "recording"
          ? t("phaseRecording")
          : phase === "saving"
            ? t("phaseSaving")
            : phase === "denied"
              ? t("phaseDenied")
              : t("phaseUnsupported");

  // Gold zeichnet die laufende Aufnahme aus — sie ist der besondere Zustand,
  // und das AImighty-Gold ist genau dafür da. Rot bleibt dem Fehler
  // vorbehalten, sonst wären „nimmt auf" und „Mikrofon verweigert" zwei
  // kaum unterscheidbare Rottöne. Das Speichern tritt als Übergang zurück.
  const dotColor =
    phase === "recording"
      ? "var(--am-gold-500)"
      : phase === "saving"
        ? "var(--am-text-gedaempft)"
        : phase === "denied" || phase === "unsupported"
          ? "var(--am-fehler)"
          : "var(--am-text-deaktiviert)";

  const pulsing =
    phase === "recording" || phase === "requesting" || phase === "saving";

  return (
    <p className="mono inline-flex items-center gap-2 text-xs uppercase tracking-[0.08em] text-text-gedaempft">
      <span
        aria-hidden
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{
          background: dotColor,
          animation: pulsing ? "blink 1s ease-in-out infinite" : undefined,
        }}
      />
      {label}
    </p>
  );
}

function Notice({
  title,
  body,
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="mt-8 rounded-lg border border-trennlinie bg-seite p-6 text-left">
      <p className="font-display text-lg font-medium">{title}</p>
      <p className="mt-2 text-sm text-text-sekundaer">{body}</p>
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="btn btn-sekundaer mt-4"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

/**
 * Die Zusage unter dem Aufnahme-Knopf — aus dem gemessenen Zustand, nicht
 * aus einer Behauptung.
 *
 * Bis hierher stand an dieser Stelle pauschal „Audio, Transkript und
 * Suchindex bleiben auf Ihrer Olares-Box". Das stimmt nur, solange das
 * Sprachmodell in der Box liegt. Ist ein externer Endpunkt eingetragen,
 * geht das Transkript zur Zusammenfassung hinaus — und ausgerechnet an
 * der prominentesten Stelle stand das Gegenteil.
 *
 * Audio und Suchindex bleiben in jeder Konfiguration hier; nur das
 * Transkript und die fertigen Protokolle können die Box verlassen. Die
 * Texte trennen das sauber, statt pauschal zu beruhigen.
 */
function Datensouveraenitaet() {
  const t = useTranslations("recording");
  const lage = useEgress();

  // Nicht abrufbar: nichts sagen. Eine Zusage ohne Beleg ist schlechter
  // als gar keine — dieselbe Regel wie beim Nachweis in der Navigation.
  if (lage === null) return null;

  const { llm_extern, llm_host, alles_bleibt } = lage;

  const titel = llm_extern
    ? t("trustLlmTitel")
    : alles_bleibt
      ? t("trustAllesTitel")
      : t("trustZieleTitel");

  const text = llm_extern
    ? t("trustLlmText", { host: llm_host ?? "" })
    : alles_bleibt
      ? t("trustAllesText")
      : t("trustZieleText");

  return (
    <div className="mt-16 flex flex-col items-center gap-3">
      <div
        className="flex h-10 w-10 items-center justify-center rounded-full"
        style={
          llm_extern
            ? {
                background: "var(--am-achtung-flaeche)",
                border: "1px solid var(--am-achtung-rand)",
              }
            : {
                background: "var(--am-gold-200)",
                border: "1px solid rgba(201, 169, 97, 0.4)",
              }
        }
      >
        {llm_extern ? (
          <ShieldAlert
            className="h-5 w-5"
            style={{ color: "var(--am-achtung)" }}
            strokeWidth={1.75}
            aria-hidden
          />
        ) : (
          <ShieldCheck
            className="h-5 w-5"
            style={{ color: "var(--am-gold-beschriftung)" }}
            strokeWidth={1.75}
            aria-hidden
          />
        )}
      </div>
      <div className="max-w-[360px] text-center">
        <p className="text-sm font-medium text-text-primaer">{titel}</p>
        <p className="mt-1 text-sm text-text-gedaempft">{text}</p>
        {!alles_bleibt && (
          <Link
            href="/datenschutz"
            className="mt-2 inline-block text-sm underline text-text-sekundaer hover:text-text-primaer"
          >
            {t("trustMehr")}
          </Link>
        )}
      </div>
    </div>
  );
}
