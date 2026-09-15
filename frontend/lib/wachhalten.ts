/**
 * Den Bildschirm wach halten, solange aufgenommen oder gesendet wird.
 *
 * Sperrt sich ein Telefon mitten in einer Besprechung, halten viele mobile
 * Browser den Tab an: der Recorder pausiert oder endet, ein laufender Upload
 * bricht ab. Die Schnellnotiz hatte dafür eine Wake-Lock-Sperre, der normale
 * Aufnahmeblock nicht — ausgerechnet dort, wo Besprechungen von 90 Minuten
 * aufgenommen werden. Und beide hatten dieselbe Lücke: der Browser gibt die
 * Sperre von selbst frei, sobald der Tab kurz verdeckt ist (Benachrichtigung,
 * App-Wechsel), und niemand holte sie zurück.
 *
 * Verfügbar ab Chrome 84 und Safari 16.4, in einer auf dem Startbildschirm
 * abgelegten iOS-App erst ab etwa iOS 18.4. Wo es fehlt, meldet
 * `verfuegbar` das, und die Oberfläche bittet, den Bildschirm nicht zu
 * sperren.
 */
import { useEffect, useRef, useState } from "react";

type Sperre = { release(): Promise<void>; addEventListener?(typ: "release", f: () => void): void };
type NavigatorArtig = { wakeLock?: { request(typ: "screen"): Promise<Sperre> } };
type DocumentArtig = {
  visibilityState: string;
  addEventListener(typ: "visibilitychange", f: () => void): void;
  removeEventListener(typ: "visibilitychange", f: () => void): void;
};

export class Wachhalter {
  private aktiv = false;
  private sperre: Sperre | null = null;
  private fordertAn = false;
  /** Ob der Browser die Sperre überhaupt kennt und sie zuletzt gewährt hat. */
  verfuegbar: boolean;

  constructor(
    private readonly nav: NavigatorArtig,
    private readonly doc: DocumentArtig,
    private readonly beiAenderung: (verfuegbar: boolean) => void = () => {},
  ) {
    this.verfuegbar = Boolean(nav.wakeLock);
  }

  private readonly sichtbarkeit = () => {
    if (this.aktiv && this.doc.visibilityState === "visible") void this.anfordern();
  };

  an(): void {
    if (this.aktiv) return;
    this.aktiv = true;
    this.doc.addEventListener("visibilitychange", this.sichtbarkeit);
    void this.anfordern();
  }

  aus(): void {
    if (!this.aktiv) return;
    this.aktiv = false;
    this.doc.removeEventListener("visibilitychange", this.sichtbarkeit);
    const sperre = this.sperre;
    this.sperre = null;
    void sperre?.release().catch(() => {});
  }

  private setzeVerfuegbar(wert: boolean) {
    if (this.verfuegbar === wert) return;
    this.verfuegbar = wert;
    this.beiAenderung(wert);
  }

  private async anfordern(): Promise<void> {
    if (!this.nav.wakeLock) {
      this.setzeVerfuegbar(false);
      return;
    }
    // Verdeckt lehnt der Browser ab; `visibilitychange` holt es nach.
    if (this.sperre || this.fordertAn || this.doc.visibilityState !== "visible") return;
    this.fordertAn = true;
    try {
      const sperre = await this.nav.wakeLock.request("screen");
      if (!this.aktiv) {
        // Während der Anfrage ist die Aufnahme zu Ende gegangen.
        void sperre.release().catch(() => {});
        return;
      }
      this.sperre = sperre;
      sperre.addEventListener?.("release", () => {
        if (this.sperre === sperre) this.sperre = null;
      });
      this.setzeVerfuegbar(true);
    } catch {
      this.setzeVerfuegbar(false);
    } finally {
      this.fordertAn = false;
    }
  }
}

/**
 * Hält den Bildschirm wach, solange `aktiv` gilt. Gibt zurück, ob das
 * gelingt — `false` heißt: den Nutzer bitten, nicht zu sperren.
 */
export function useWachhalten(aktiv: boolean): boolean {
  const halter = useRef<Wachhalter | null>(null);
  const [verfuegbar, setVerfuegbar] = useState(true);

  useEffect(() => {
    const h = new Wachhalter(
      navigator as unknown as NavigatorArtig,
      document,
      setVerfuegbar,
    );
    halter.current = h;
    setVerfuegbar(h.verfuegbar);
    return () => {
      h.aus();
      halter.current = null;
    };
  }, []);

  useEffect(() => {
    if (aktiv) halter.current?.an();
    else halter.current?.aus();
  }, [aktiv]);

  return verfuegbar;
}
