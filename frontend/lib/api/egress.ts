import { apiGet } from "./client";

export type EgressZiel = {
  art: "llm" | "webhook";
  host: string;
  beschreibung: string;
};

export type EgressRead = {
  /** Kernaussage für den Nachweis in der Navigation. */
  alles_bleibt: boolean;
  llm_extern: boolean;
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
