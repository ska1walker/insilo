"use client";

import { Loader2, Mic, ShieldAlert, ShieldCheck, Square, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { AufnahmeWelle } from "@/components/aufnahme-welle";
import { useFortschrittText, useSendefehler } from "@/components/offene-aufnahmen";
import { RecordingIndicator } from "@/components/recording-indicator";
import { useToast } from "@/components/toast";
import { ApiError } from "@/lib/api/client";
import { useEgress } from "@/lib/api/egress";
import type { Fortschritt } from "@/lib/api/hochladen";
import { createMeeting } from "@/lib/api/meetings";
import { listTemplates, type TemplateDto } from "@/lib/api/templates";
import { ASR_AUDIO_CONSTRAINTS, ASR_RECORDER_OPTIONS } from "@/lib/audio";
import {
  ANNEHMBAR,
  aufnahmeDatumFuerDatei,
  dauerAusMetadaten,
  MAX_UPLOAD_MB,
  mimeFuerDatei,
  pruefeDatei,
  titelAusDateiname,
} from "@/lib/audiodatei";
import { alsGescheitertAblegen, senden, Sicherung } from "@/lib/aufnahmen";
import { defaultMeetingTitle, formatDuration } from "@/lib/format";
import { useWachhalten } from "@/lib/wachhalten";

const DEFAULT_TEMPLATE_ID = "00000000-0000-0000-0000-000000000001";

const AUDIO_LANGUAGE_OPTIONS = ["auto", "de", "en", "fr", "es", "it"] as const;
type AudioLanguage = (typeof AUDIO_LANGUAGE_OPTIONS)[number];

type Phase =
  | "idle"
  | "requesting"
  | "recording"
  | "saving"
  | "uploading"
  | "denied"
  | "unsupported";

/**
 * Eine hochgeladene Datei, deren Senden scheiterte. Anders als eine Aufnahme
 * geht dabei nichts verloren — die Datei liegt ja noch auf dem Gerät. Darum
 * keine Sicherung und kein Eintrag in der Liste über den Ansichten, nur ein
 * Hinweis hier mit „Erneut versuchen" und „Andere Datei wählen".
 */
type DateiFehler = { datei: File | null; kennung: string; fehler: string };

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
  const sicherungRef = useRef<Sicherung | null>(null);
  const aktivRef = useRef(true);
  const sendefehler = useSendefehler();
  const fortschrittText = useFortschrittText();
  const toast = useToast();
  const [fortschritt, setFortschritt] = useState<Fortschritt | null>(null);
  const dateiRef = useRef<HTMLInputElement | null>(null);
  const [dateiFehler, setDateiFehler] = useState<DateiFehler | null>(null);
  const [dateiName, setDateiName] = useState<string | null>(null);

  // Sperrt sich das Telefon, halten mobile Browser den Tab an — der
  // Recorder pausiert, ein Upload bricht ab. Auch beim Senden wach bleiben.
  const wach = useWachhalten(
    phase === "recording" || phase === "saving" || phase === "uploading",
  );

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
    aktivRef.current = true;
    return () => {
      aktivRef.current = false;
      stopTracksAndTick();
      // Wer die Ansicht mitten in der Aufnahme verlässt, beendet sie. Was
      // bis dahin geschrieben ist, bleibt und erscheint in der Liste über
      // jeder Ansicht.
      sicherungRef.current?.loslassen();
    };
  }, []);

  // Solange eine Aufnahme läuft oder gesendet wird, fragt der Browser vor
  // dem Schließen nach. Gescheiterte bewacht die Liste in der Hülle. Beim
  // Hochladen einer Datei geht zwar nichts verloren, aber ein halb
  // gesendeter Upload von 500 MB soll nicht still abbrechen.
  const ungesichert =
    phase === "recording" || phase === "saving" || phase === "uploading";
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
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setLiveStream(null);
  }

  async function startRecording() {
    setError(null);
    setDateiFehler(null);
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
      const sicherung = await Sicherung.beginnen({
        mimeType: mime,
        titel: defaultMeetingTitle(Date.now(), locale, t("defaultTitlePrefix")),
        templateId: selectedTemplate,
        audioLanguage,
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
      tickRef.current = window.setInterval(() => {
        setElapsed(Date.now() - startedAtRef.current);
      }, 250);
    } catch (err) {
      console.error("getUserMedia failed", err);
      stopTracksAndTick();
      // Gescheitert, nachdem die Sicherung schon angelegt war: sie ist leer
      // und hielte sonst die Sperre bis zum Schließen des Tabs.
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
      const meeting = await senden(sicherung.kopf, ton, setFortschritt);
      sicherung.loslassen();
      // Wer die Ansicht während des Sendens verlassen hat, bleibt, wo er ist.
      if (aktivRef.current) router.push(`/m/${meeting.id}`);
    } catch (err) {
      // Früher stand hier `setPhase("idle")` und eine Zeile Fehlertext —
      // und die Aufnahme lag nur noch in `chunksRef`, bis zum nächsten
      // Start oder Seitenwechsel. So ging am 14.9.2026 eine Besprechung
      // von 90 Minuten verloren. Jetzt übernimmt die Liste in der Hülle,
      // mit dem vollständigen Ton aus dem Arbeitsspeicher — auch über
      // Seitenwechsel hinweg.
      console.error("upload failed", err);
      alsGescheitertAblegen({ sicherung, ton, fehler: sendefehler(err) });
      if (aktivRef.current) {
        setPhase("idle");
        setElapsed(0);
      }
    } finally {
      setFortschritt(null);
    }
  }

  /**
   * Eine vorhandene Datei hochladen — mit der gewählten Vorlage und Sprache.
   * Braucht kein Mikrofon und steht deshalb auch bei verweigertem oder
   * fehlendem Mikrofonzugang bereit.
   */
  async function dateiHochladen(datei: File, kennung: string = crypto.randomUUID()) {
    const zurueck: Phase =
      phase === "denied" || phase === "unsupported" ? phase : "idle";
    setError(null);
    setDateiFehler(null);

    const mime = mimeFuerDatei(datei.name, datei.type);
    const pruefung = pruefeDatei(datei.size, mime);
    if (pruefung !== "ok") {
      setDateiFehler({
        datei: null,
        kennung,
        fehler:
          pruefung === "zuGross"
            ? t("dateiZuGross", { max: MAX_UPLOAD_MB })
            : t("dateiKeinAudio"),
      });
      return;
    }

    setPhase("uploading");
    setDateiName(datei.name);
    setFortschritt(null);
    try {
      // Eine Datei aus einem Cloud-Ordner kann unlesbar geworden sein. Ohne
      // diese Probe meldete der Upload „Box nicht erreichbar".
      try {
        await datei.slice(0, 1).arrayBuffer();
      } catch {
        setDateiFehler({ datei: null, kennung, fehler: t("dateiUnlesbar") });
        setPhase(zurueck);
        return;
      }
      const meeting = await createMeeting({
        blob: datei,
        title: titelAusDateiname(datei.name, locale, t("defaultTitlePrefix")),
        durationMs: await dauerAusMetadaten(datei),
        mimeType: mime,
        templateId: selectedTemplate,
        audioLanguage,
        dateiname: datei.name,
        beiFortschritt: setFortschritt,
        // Dieselbe Kennung bei „Erneut versuchen" — kam der erste Versuch an,
        // gibt die Box die Besprechung zurück, statt eine zweite anzulegen.
        clientId: kennung,
        aufnahmeBeginn: aufnahmeDatumFuerDatei(datei.name, datei.lastModified),
      });
      if (aktivRef.current) router.push(`/m/${meeting.id}`);
    } catch (err) {
      console.error("file upload failed", err);
      if (!aktivRef.current) {
        // Schon woanders: ohne Meldung hielte man die Datei für angekommen
        // und löschte sie vielleicht. Die Kurzmeldung steht, bis jemand sie
        // schließt.
        toast.show({ message: `${datei.name}: ${sendefehler(err)}`, variant: "error" });
        return;
      }
      // Zu groß bleibt zu groß — dann kein „Erneut versuchen".
      const wiederholbar = !(err instanceof ApiError && err.status === 413);
      setDateiFehler({
        datei: wiederholbar ? datei : null,
        kennung,
        fehler: sendefehler(err),
      });
      setPhase(zurueck);
    } finally {
      setFortschritt(null);
    }
  }

  const dateiWaehlen = () => dateiRef.current?.click();

  const dateiKnopf = (
    <button type="button" className="btn btn-still" onClick={dateiWaehlen}>
      <Upload className="h-4 w-4" strokeWidth={1.75} aria-hidden />
      {t("dateiHochladen")}
    </button>
  );

  function cancel() {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = null;
      // Beim Stoppen liefert der Recorder noch ein letztes Stück; es darf
      // weder in den Speicher noch in die Sicherung.
      recorder.ondataavailable = null;
      try {
        recorder.stop();
      } catch {
        /* ignore */
      }
    }
    chunksRef.current = [];
    stopTracksAndTick();
    // Abbrechen ist die ausdrückliche Absage — die Sicherung geht mit.
    void sicherungRef.current?.absagen();
    sicherungRef.current = null;
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
        <input
          ref={dateiRef}
          type="file"
          accept={ANNEHMBAR}
          className="hidden"
          aria-hidden
          tabIndex={-1}
          onChange={(e) => {
            const datei = e.target.files?.[0];
            // Zurücksetzen, damit dieselbe Datei ein zweites Mal wählbar ist.
            e.target.value = "";
            if (datei) void dateiHochladen(datei);
          }}
        />

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

        {phase === "recording" && !wach && (
          <p className="-mt-6 mb-8 text-sm text-text-gedaempft" role="note">
            {t("bildschirmWach")}
          </p>
        )}

        {phase === "saving" && <div className="mb-10" />}

        {phase === "uploading" && (
          <p className="mt-3 mb-10 truncate text-sm text-text-sekundaer">
            {dateiName}
          </p>
        )}

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

        {(phase === "saving" || phase === "uploading") && (
          <>
            <button
              type="button"
              className={`btn-record${phase === "saving" ? " recording" : ""}`}
              disabled
              aria-label={t("saving")}
            >
              <Loader2
                className="btn-record-icon animate-spin"
                strokeWidth={1.5}
              />
            </button>
            <p
              className="mono mt-5 text-sm tabular-nums text-text-sekundaer"
              aria-live="polite"
            >
              {fortschrittText(fortschritt) ?? t("saving")}
            </p>
          </>
        )}

        {phase === "idle" && (
          <p className="mt-5 text-sm text-text-gedaempft">{t("phaseIdle")}</p>
        )}

        {dateiFehler &&
          (phase === "idle" || phase === "denied" || phase === "unsupported") && (
            <div className="streifen streifen-achtung mt-6 text-left" role="alert">
              <span className="zeichen" aria-hidden>
                !
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm">{dateiFehler.fehler}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {dateiFehler.datei && (
                    <button
                      type="button"
                      className="btn btn-sekundaer"
                      onClick={() => {
                        const { datei, kennung } = dateiFehler;
                        if (datei) void dateiHochladen(datei, kennung);
                      }}
                    >
                      {t("dateiErneut")}
                    </button>
                  )}
                  <button type="button" className="btn btn-still" onClick={dateiWaehlen}>
                    {t("dateiAndere")}
                  </button>
                </div>
              </div>
            </div>
          )}

        {phase === "idle" && !dateiFehler && <div className="mt-4">{dateiKnopf}</div>}

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

        {(phase === "denied" || phase === "unsupported") && !dateiFehler && (
          <div className="mt-4">{dateiKnopf}</div>
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
            : phase === "uploading"
              ? t("phaseUploading")
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
      : phase === "saving" || phase === "uploading"
        ? "var(--am-text-gedaempft)"
        : phase === "denied" || phase === "unsupported"
          ? "var(--am-fehler)"
          : "var(--am-text-deaktiviert)";

  const pulsing =
    phase === "recording" ||
    phase === "requesting" ||
    phase === "saving" ||
    phase === "uploading";

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

  const { llm_extern, llm_eigene_box, llm_fehlt, llm_host, alles_bleibt } = lage;
  const { stt_extern, stt_host } = lage;

  // Fehlt der Endpunkt, ist das kein Datenschutz-Thema, sondern eine
  // offene Einrichtung — sie hat Vorrang vor der Herkunftsaussage.
  // Reihenfolge nach Gewicht: dass die Tonaufnahme selbst hinausgeht,
  // muss jemand wissen, BEVOR er aufnimmt — das schlägt jede offene
  // Einrichtung und jedes Transkript-Ziel.
  const titel = stt_extern
    ? t("trustSttTitel", { host: stt_host ?? "" })
    : llm_fehlt
    ? t("llmFehltKurz")
    : llm_extern
    ? t("trustLlmTitel")
    : llm_eigene_box
      ? t("trustEigeneBoxTitel")
      : alles_bleibt
        ? t("trustAllesTitel")
        : t("trustZieleTitel");

  const text = stt_extern
    ? t("trustSttText")
    : llm_fehlt
    ? t("trustAllesText")
    : llm_extern
    ? t("trustLlmText", { host: llm_host ?? "" })
    : llm_eigene_box
      ? t("trustEigeneBoxText")
      : alles_bleibt
        ? t("trustAllesText")
        : t("trustZieleText");

  return (
    <div className="mt-16 flex flex-col items-center gap-3">
      <div
        className="flex h-10 w-10 items-center justify-center rounded-full"
        style={
          stt_extern || llm_extern
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
        {(!alles_bleibt || llm_eigene_box) && (
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
