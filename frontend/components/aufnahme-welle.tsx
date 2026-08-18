"use client";

/**
 * Die Welle während der Aufnahme.
 *
 * Zeigt das echte Mikrofonsignal, nicht eine Zierschleife: das
 * Designsystem verlangt Animationen, die etwas leisten. Hier ist das der
 * Nachweis, dass das Mikrofon wirklich Signal bekommt — bei einer
 * Aufnahme-App die einzige Rückmeldung, die zählt. Eine erfundene
 * Bewegung wäre schlimmer als keine: sie würde auch dann laufen, wenn
 * das Mikrofon stumm ist.
 *
 * Gezeichnet wird ein mitlaufender Pegelverlauf — neue Werte rechts, der
 * ältere Verlauf wandert nach links, wie bei einem Schreiber. Das zeigt
 * nicht nur „da ist Signal", sondern auch, ob die letzten Sekunden
 * brauchbar waren.
 *
 * Gold, weil das Markensystem die laufende Aufnahme als Auszeichnung
 * führt (siehe docs/DESIGN.md §3).
 */

import { useEffect, useRef } from "react";

/** Wie viele Pegelwerte der Verlauf hält. */
const BALKEN = 56;
const BALKEN_BREITE = 3;
const BALKEN_ABSTAND = 2;

export function AufnahmeWelle({
  stream,
  hoehe = 48,
  className = "",
}: {
  stream: MediaStream | null;
  hoehe?: number;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pegelRef = useRef<number[]>(new Array(BALKEN).fill(0));

  useEffect(() => {
    if (!stream) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    // Wer Bewegung reduziert haben will, bekommt den Verlauf still: der
    // Pegel wird weiter gemessen und gezeichnet, aber ohne Nachführung
    // pro Bild — nur alle 250 ms ein Schritt.
    const wenigerBewegung = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    if (!AudioCtx) return;

    const ctx = new AudioCtx();
    const quelle = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    // Klein halten: wir brauchen keine Frequenzauflösung, nur den Pegel.
    analyser.fftSize = 1024;
    quelle.connect(analyser);

    const puffer = new Uint8Array(analyser.fftSize);
    const zeichenCtx = canvas.getContext("2d");
    if (!zeichenCtx) return;

    let laeuft = true;
    let letzterSchritt = 0;

    // Anzeigebereich in Dezibel. Unterhalb von -60 dB ist Raumstille,
    // oberhalb von -6 dB wird es laut — dazwischen spielt sich Sprache ab.
    const DB_STILL = -60;
    const DB_LAUT = -6;

    /**
     * Pegel als Wert zwischen 0 und 1.
     *
     * Bewusst logarithmisch: ein linearer Faktor sättigt schon bei
     * halber Aussteuerung, dann steht die Anzeige beim Sprechen dauerhaft
     * am Anschlag und zeigt nichts mehr an. Lautstärke wird ohnehin
     * logarithmisch wahrgenommen — deshalb rechnen Pegelanzeigen in dB.
     */
    function pegel(): number {
      analyser.getByteTimeDomainData(puffer);
      let summe = 0;
      for (let i = 0; i < puffer.length; i++) {
        const v = (puffer[i] - 128) / 128;
        summe += v * v;
      }
      const rms = Math.sqrt(summe / puffer.length);
      if (rms < 1e-5) return 0;
      const db = 20 * Math.log10(rms);
      const norm = (db - DB_STILL) / (DB_LAUT - DB_STILL);
      return Math.max(0, Math.min(1, norm));
    }

    // Canvas und Kontext werden durchgereicht: TypeScript hält die
    // Nicht-Null-Prüfung von oben in dieser Schleifen-Funktion sonst nicht.
    function zeichne(
      zeit: number,
      flaeche: HTMLCanvasElement,
      stift: CanvasRenderingContext2D,
    ) {
      if (!laeuft) return;

      const schrittWeite = wenigerBewegung ? 250 : 60;
      if (zeit - letzterSchritt >= schrittWeite) {
        letzterSchritt = zeit;
        pegelRef.current.push(pegel());
        if (pegelRef.current.length > BALKEN) pegelRef.current.shift();
      }

      const dpr = window.devicePixelRatio || 1;
      const breite = BALKEN * (BALKEN_BREITE + BALKEN_ABSTAND);
      if (flaeche.width !== breite * dpr) {
        flaeche.width = breite * dpr;
        flaeche.height = hoehe * dpr;
        flaeche.style.width = `${breite}px`;
        flaeche.style.height = `${hoehe}px`;
      }
      stift.setTransform(dpr, 0, 0, dpr, 0, 0);
      stift.clearRect(0, 0, breite, hoehe);

      // Farben aus den Token lesen, damit der Dunkelmodus mitzieht —
      // Canvas kennt keine CSS-Variablen.
      const wurzel = getComputedStyle(document.documentElement);
      const gold = wurzel.getPropertyValue("--am-gold-500").trim() || "#caa960";
      const ruhig =
        wurzel.getPropertyValue("--am-text-deaktiviert").trim() || "#819bb7";

      const mitte = hoehe / 2;
      pegelRef.current.forEach((p, i) => {
        const x = i * (BALKEN_BREITE + BALKEN_ABSTAND);
        // Mindesthöhe, damit die Linie auch bei Stille als Linie lesbar
        // bleibt statt zu verschwinden.
        const h = Math.max(2, p * (hoehe - 4));
        stift.fillStyle = p > 0.04 ? gold : ruhig;
        stift.beginPath();
        stift.roundRect(x, mitte - h / 2, BALKEN_BREITE, h, 1.5);
        stift.fill();
      });

      id = requestAnimationFrame((t) => zeichne(t, flaeche, stift));
    }

    let id = requestAnimationFrame((t) => zeichne(t, canvas, zeichenCtx));

    return () => {
      laeuft = false;
      cancelAnimationFrame(id);
      quelle.disconnect();
      // Den Kontext schließen, sonst bleibt pro Aufnahme einer offen —
      // Browser begrenzen die Zahl der AudioContexts pro Seite.
      void ctx.close();
      pegelRef.current = new Array(BALKEN).fill(0);
    };
  }, [stream, hoehe]);

  if (!stream) return null;

  return (
    <canvas
      ref={canvasRef}
      className={className}
      // Der Verlauf ist Beiwerk zur Statuszeile („nimmt auf") und zum
      // Timer, die beide vorgelesen werden. Doppelt ansagen hilft nicht.
      aria-hidden
    />
  );
}
