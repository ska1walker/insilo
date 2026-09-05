/**
 * Protokoll — wer hat wann was geändert oder ausgeleitet.
 *
 * Gegenstück zu `backend/app/routers/protokoll.py`. Geschrieben wird das
 * Protokoll aus einer Middleware im Backend; hier wird nur gelesen.
 */

import { apiGet } from "./client";

export type ProtokollEintrag = {
  id: string;
  zeitpunkt: string;
  aktion: string;
  /** Olares-Benutzername oder Name des Zugriffsschlüssels. */
  urheber: string | null;
  urheber_art: "user" | "api_key" | "unbekannt";
  art: string | null;
  kennung: string | null;
  /** Titel der Besprechung — null, wenn sie inzwischen entfernt wurde. */
  bezeichnung: string | null;
  erfolg: boolean;
  /** Vorgang, bei dem Inhalte die Box verlassen können. */
  ausleitung: boolean;
  herkunft: string | null;
  zusatz: Record<string, unknown>;
};

export type ProtokollSeite = {
  eintraege: ProtokollEintrag[];
  hat_mehr: boolean;
  /** Falsch für einfache Mitglieder: die sehen nur ihre eigenen Vorgänge. */
  darf_alles_sehen: boolean;
};

export type ProtokollAuswahl = {
  aktionen: string[];
  ausleitung: string[];
};

export async function fetchProtokollAuswahl(): Promise<ProtokollAuswahl> {
  return apiGet<ProtokollAuswahl>("/api/v1/protokoll/auswahl");
}

export async function fetchProtokoll(opts: {
  aktionen?: string[];
  nurAusleitung?: boolean;
  anzahl?: number;
  ab?: number;
} = {}): Promise<ProtokollSeite> {
  const p = new URLSearchParams();
  for (const a of opts.aktionen ?? []) p.append("aktion", a);
  if (opts.nurAusleitung) p.set("nur_ausleitung", "true");
  if (opts.anzahl !== undefined) p.set("anzahl", String(opts.anzahl));
  if (opts.ab !== undefined) p.set("ab", String(opts.ab));
  const qs = p.toString();
  return apiGet<ProtokollSeite>(`/api/v1/protokoll${qs ? `?${qs}` : ""}`);
}
