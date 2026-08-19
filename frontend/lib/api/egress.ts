"use client";

import { useEffect, useState } from "react";
import { apiGet } from "./client";

export type EgressZiel = {
  art: "llm" | "webhook";
  host: string;
  beschreibung: string;
};

export type EgressRead = {
  /** Kernaussage für den Nachweis in der Navigation. */
  alles_bleibt: boolean;
  /** true nur bei einem fremden Anbieter. */
  llm_extern: boolean;
  /** Die eigene Box unter ihrer öffentlichen Adresse — kein Dritter. */
  llm_eigene_box: boolean;
  /** Kein Endpunkt eingetragen: Zusammenfassungen laufen nicht. */
  llm_fehlt: boolean;
  llm_host: string | null;
  webhooks_aktiv: number;
  ziele: EgressZiel[];
  /**
   * null = es gab nie eine Zustellung. Bewusst nicht 0 — das Paket
   * verlangt gemessene Werte, und "noch nichts gesendet" ist etwas
   * anderes als "0 Byte gemessen".
   */
  gesendete_bytes: number | null;
  zustellungen: number;
  letzter_versand: string | null;
};

export function fetchEgress(): Promise<EgressRead> {
  return apiGet<EgressRead>("/api/v1/egress");
}

/**
 * Lädt den Egress-Zustand für eine Ansicht.
 *
 * `null` heißt „noch nicht da oder nicht abrufbar" — beides führt zur
 * selben Konsequenz: nichts behaupten. Wer diesen Hook benutzt, muss den
 * Fall abfangen, statt einen Ersatztext anzuzeigen.
 */
export function useEgress(): EgressRead | null {
  const [lage, setLage] = useState<EgressRead | null>(null);

  useEffect(() => {
    let abgebrochen = false;
    fetchEgress()
      .then((l) => !abgebrochen && setLage(l))
      .catch(() => {
        /* nicht abrufbar — bleibt null, die Ansicht schweigt */
      });
    return () => {
      abgebrochen = true;
    };
  }, []);

  return lage;
}
