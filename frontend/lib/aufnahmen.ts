/**
 * Aufnahmen auf dem Gerät sichern, bis die Box sie bestätigt hat.
 *
 * **Warum.** Am 14.9.2026 ging eine 90-Minuten-Besprechung verloren. Die
 * Tonstücke lagen nur im Arbeitsspeicher des Tabs; der Upload scheiterte
 * (siehe `app/api/v1/recordings/route.ts`), und damit war die Aufnahme
 * weg, sobald jemand die Seite verließ. Nichts im Browser hielt sie fest.
 *
 * **Was hier passiert.** Jede Sekunde schreibt der Recorder ein Stück in
 * IndexedDB, nicht erst am Ende. Gelöscht wird es erst, wenn die Box die
 * Besprechung mit 201 angelegt hat. Stürzt der Tab ab, geht der Akku aus
 * oder scheitert das Senden, liegt die Aufnahme bis dahin vollständig auf
 * dem Gerät und `components/offene-aufnahmen.tsx` bietet sie an.
 *
 * **Wer gerade daran arbeitet.** Eine laufende oder gerade gesendete
 * Aufnahme darf niemand anderes anbieten, sonst entstünde sie doppelt.
 * Dafür hält der Tab eine Web-Lock-Sperre pro Aufnahme; sie fällt von
 * selbst, wenn der Tab schließt oder abstürzt. Ohne Web Locks gilt eine
 * Aufnahme als verwaist, wenn ihr letztes Stück älter als
 * `VERWAIST_NACH_MS` ist.
 *
 * Gespeichert werden `ArrayBuffer`, keine `Blob`s: ältere Safari-Fassungen
 * konnten Blobs in IndexedDB nicht zuverlässig ablegen.
 */
import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { Fortschritt } from "@/lib/api/hochladen";
import { createMeeting, type MeetingDto } from "@/lib/api/meetings";

export type AufnahmeKopf = {
  id: string;
  /** Beginn der Aufnahme, ms seit 1970. */
  begonnen: number;
  /** Zeitpunkt des zuletzt geschriebenen Stücks. */
  zuletzt: number;
  mimeType: string;
  titel: string;
  stuecke: number;
  bytes: number;
  /** Gemessene Dauer beim Stopp; fehlt, wenn der Tab vorher endete. */
  dauerMs: number | null;
  /**
   * Ein Stück ließ sich nicht schreiben (meist: Speicher voll). Gesichert
   * ist dann nur der Anfang bis `zuletzt` — und genau das muss dastehen,
   * statt einen gekürzten Rest als die ganze Aufnahme anzubieten.
   */
  unvollstaendig?: boolean;
  templateId?: string;
  audioLanguage?: string;
  quickMode?: boolean;
};

export type AufnahmeAngaben = Pick<
  AufnahmeKopf,
  "mimeType" | "titel" | "templateId" | "audioLanguage" | "quickMode"
>;

type Stueck = { id: string; nr: number; daten: ArrayBuffer };

interface AufnahmenDB extends DBSchema {
  koepfe: { key: string; value: AufnahmeKopf };
  stuecke: { key: [string, number]; value: Stueck };
}

const DB_NAME = "insilo-aufnahmen";
const KANAL = "insilo-aufnahmen";
const SPERRE = "insilo-aufnahme-";
export const VERWAIST_NACH_MS = 15_000;

let dbPromise: Promise<IDBPDatabase<AufnahmenDB>> | null = null;

function db() {
  if (!dbPromise) {
    dbPromise = openDB<AufnahmenDB>(DB_NAME, 1, {
      upgrade(d) {
        d.createObjectStore("koepfe", { keyPath: "id" });
        d.createObjectStore("stuecke", { keyPath: ["id", "nr"] });
      },
    });
    // Ein gescheitertes Öffnen soll beim nächsten Versuch neu probiert
    // werden, nicht für immer als verworfenes Promise hängen bleiben.
    dbPromise.catch(() => {
      dbPromise = null;
    });
  }
  return dbPromise;
}

function alleStuecke(id: string) {
  return IDBKeyRange.bound([id, 0], [id, Number.MAX_SAFE_INTEGER]);
}

let sender: BroadcastChannel | null = null;

function melden() {
  if (typeof BroadcastChannel === "undefined") return;
  sender ??= new BroadcastChannel(KANAL);
  sender.postMessage("geaendert");
  // BroadcastChannel erreicht andere Objekte, auch im selben Tab — nur
  // nicht den Absender selbst. Ein Ereignis am Fenster deckt den Rest ab.
  window.dispatchEvent(new Event(KANAL));
}

/** Ruft `rueckruf` bei jeder Änderung, auch aus anderen Tabs. */
export function beiAenderung(rueckruf: () => void): () => void {
  const kanal =
    typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(KANAL);
  if (kanal) kanal.onmessage = rueckruf;
  window.addEventListener(KANAL, rueckruf);
  return () => {
    kanal?.close();
    window.removeEventListener(KANAL, rueckruf);
  };
}

let dauerhaftAngefragt = false;

/**
 * Bittet den Browser, die Sicherungen nicht von selbst zu räumen. Ohne das
 * darf er IndexedDB bei Platzmangel leeren — samt einer nicht gesendeten
 * Aufnahme. Einmal pro Tab, ohne zu warten; eine Absage ändert nichts am
 * Aufnehmen. Firefox fragt dabei nach, Chrome und Safari entscheiden still.
 */
function dauerhaftAnfragen(): void {
  if (dauerhaftAngefragt || typeof navigator === "undefined") return;
  dauerhaftAngefragt = true;
  const speicher = navigator.storage;
  if (!speicher?.persist || !speicher.persisted) return;
  void speicher
    .persisted()
    .then((schon) => (schon ? true : speicher.persist()))
    .catch(() => {});
}

function locks(): LockManager | null {
  return typeof navigator !== "undefined" && "locks" in navigator
    ? navigator.locks
    : null;
}

// ─── Reine Regeln (getestet in aufnahmen.test.ts) ─────────────────────

/**
 * Gehört die Aufnahme niemandem mehr? Mit Web Locks entscheidet die
 * Sperre; ohne sie das Alter des letzten Stücks.
 */
export function istVerwaist(
  kopf: AufnahmeKopf,
  gesperrt: Set<string> | null,
  jetzt: number,
): boolean {
  if (gesperrt) return !gesperrt.has(SPERRE + kopf.id);
  return jetzt - kopf.zuletzt > VERWAIST_NACH_MS;
}

/**
 * Wie lang das ist, was in IndexedDB liegt: die gemessene Dauer, sonst —
 * nach einem Absturz oder einem gescheiterten Schreiben — die Spanne bis
 * zum letzten geschriebenen Stück.
 */
export function dauerVon(kopf: AufnahmeKopf): number {
  const bisZumLetztenStueck = Math.max(0, kopf.zuletzt - kopf.begonnen);
  if (kopf.unvollstaendig) return bisZumLetztenStueck;
  return kopf.dauerMs ?? bisZumLetztenStueck;
}

export function dateinameVon(kopf: AufnahmeKopf): string {
  const endung = kopf.mimeType.includes("mp4")
    ? "m4a"
    : kopf.mimeType.includes("ogg")
      ? "ogg"
      : "webm";
  const d = new Date(kopf.begonnen);
  const p = (n: number) => String(n).padStart(2, "0");
  const stempel = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`;
  return `insilo-aufnahme-${stempel}.${endung}`;
}

// ─── Während der Aufnahme ────────────────────────────────────────────

// Wie viele Aufnahmen in diesem Tab gerade laufen. Wer nach dem Senden
// die Seite wechseln will, fragt vorher: ein Seitenwechsel beendet den
// Recorder, und der Rest der Besprechung würde nie aufgenommen.
let laufend = 0;

export function nimmtGeradeAuf(): boolean {
  return laufend > 0;
}

/**
 * Eine Aufnahme, die gerade entsteht. Schreibt jedes Stück in Reihenfolge
 * weg und hält die Sperre, bis `loslassen()` gerufen wird.
 *
 * Scheitert das Schreiben (kein Speicher, IndexedDB gesperrt), läuft die
 * Aufnahme im Arbeitsspeicher weiter; `gesichert` wird dann `false`, der
 * Kopf in IndexedDB als `unvollstaendig` markiert, und die Oberfläche
 * bietet die vollständige Datei aus dem Arbeitsspeicher zum Speichern an.
 */
export class Sicherung {
  gesichert = true;
  private nr = 0;
  private kette: Promise<void> = Promise.resolve();
  private freigeben: (() => void) | null = null;
  private abgesagt = false;
  private aktiv = true;

  private constructor(readonly kopf: AufnahmeKopf) {
    laufend++;
  }

  static async beginnen(angaben: AufnahmeAngaben): Promise<Sicherung> {
    const jetzt = Date.now();
    const s = new Sicherung({
      ...angaben,
      id: crypto.randomUUID(),
      begonnen: jetzt,
      zuletzt: jetzt,
      stuecke: 0,
      bytes: 0,
      dauerMs: null,
    });
    const lm = locks();
    if (lm) {
      await new Promise<void>((gesetzt) => {
        void lm.request(SPERRE + s.kopf.id, () => {
          gesetzt();
          return new Promise<void>((r) => (s.freigeben = r));
        });
      });
    }
    dauerhaftAnfragen();
    try {
      await (await db()).put("koepfe", s.kopf);
      melden();
    } catch (fehler) {
      console.error("recording backup unavailable", fehler);
      s.gesichert = false;
    }
    return s;
  }

  private beenden() {
    if (this.aktiv) laufend--;
    this.aktiv = false;
  }

  anhaengen(stueck: Blob): void {
    if (!this.gesichert || this.abgesagt) return;
    const nr = this.nr++;
    this.kette = this.kette.then(async () => {
      if (!this.gesichert || this.abgesagt) return;
      try {
        const daten = await stueck.arrayBuffer();
        const d = await db();
        const tx = d.transaction(["koepfe", "stuecke"], "readwrite");
        const kopf = {
          ...this.kopf,
          stuecke: nr + 1,
          bytes: this.kopf.bytes + daten.byteLength,
          zuletzt: Date.now(),
        };
        await Promise.all([
          tx.objectStore("stuecke").put({ id: this.kopf.id, nr, daten }),
          tx.objectStore("koepfe").put(kopf),
          tx.done,
        ]);
        // Erst nach dem Schreiben übernehmen: der Kopf beschreibt, was
        // wirklich in IndexedDB liegt.
        Object.assign(this.kopf, kopf);
      } catch (fehler) {
        console.error("recording backup failed", fehler);
        this.gesichert = false;
        this.kopf.unvollstaendig = true;
        try {
          await (await db()).put("koepfe", { ...this.kopf });
        } catch {
          /* dann bleibt der Kopf ohne Markierung; die Karte in diesem Tab
             sagt trotzdem „nicht gesichert" */
        }
      }
    });
  }

  /**
   * Wartet, bis jedes Stück geschrieben ist, und hält Dauer und das
   * Format fest, das der Recorder tatsächlich geliefert hat.
   */
  async abschliessen(dauerMs: number, mimeType?: string): Promise<void> {
    this.beenden();
    await this.kette;
    this.kopf.dauerMs = dauerMs;
    if (mimeType) this.kopf.mimeType = mimeType;
    if (!this.gesichert) return;
    try {
      await (await db()).put("koepfe", { ...this.kopf });
    } catch {
      this.gesichert = false;
    }
  }

  /**
   * Ausdrücklich abgebrochen: nichts mehr schreiben, warten, bis das
   * letzte Schreiben durch ist, dann löschen. In dieser Reihenfolge — sonst
   * legt das letzte Stück, das der Recorder beim Stoppen noch liefert, die
   * Aufnahme nach dem Löschen wieder an, nur ohne Anfang.
   */
  async absagen(): Promise<void> {
    this.abgesagt = true;
    this.beenden();
    await this.kette;
    try {
      await verwerfen(this.kopf.id);
    } catch {
      /* nichts gesichert — nichts zu löschen */
    }
    this.loslassen();
  }

  /**
   * Gibt die Aufnahme für andere Ansichten und Tabs frei — erst, wenn das
   * letzte Stück geschrieben ist, damit niemand einen halben Stand sendet.
   */
  loslassen(): void {
    this.beenden();
    void this.kette.then(() => {
      this.freigeben?.();
      this.freigeben = null;
      melden();
    });
  }
}

// ─── In diesem Tab gescheitert ───────────────────────────────────────

/**
 * Aufnahmen, deren Senden in diesem Tab scheiterte, samt Ton aus dem
 * Arbeitsspeicher. Sie liegen hier und nicht im Zustand einer Komponente:
 * sonst wäre die vollständige Kopie mit dem nächsten Seitenwechsel weg —
 * und ohne IndexedDB (voll, gesperrt) war sie die einzige.
 * Die Sperre hält die `Sicherung`, bis der Eintrag erledigt ist.
 */
export type Gescheitert = { sicherung: Sicherung; ton: Blob; fehler: string };

let gescheitert: Gescheitert[] = [];

export function gescheiterteImTab(): readonly Gescheitert[] {
  return gescheitert;
}

export function alsGescheitertAblegen(eintrag: Gescheitert): void {
  gescheitert = [...gescheitert, eintrag];
  melden();
}

export function gescheitertErledigt(id: string): void {
  const eintrag = gescheitert.find((g) => g.sicherung.kopf.id === id);
  gescheitert = gescheitert.filter((g) => g !== eintrag);
  if (eintrag) eintrag.sicherung.loslassen();
  else melden();
}

// ─── Nach der Aufnahme ───────────────────────────────────────────────

/**
 * Aufnahmen aus IndexedDB, die niemand gerade aufnimmt oder sendet und die
 * nicht schon als gescheitert in diesem Tab liegen — älteste zuerst.
 */
export async function offeneAufnahmen(): Promise<AufnahmeKopf[]> {
  let koepfe: AufnahmeKopf[];
  try {
    koepfe = await (await db()).getAll("koepfe");
  } catch {
    return [];
  }
  const lm = locks();
  const gesperrt = lm
    ? new Set(((await lm.query()).held ?? []).map((l) => l.name ?? ""))
    : null;
  const imTab = new Set(gescheitert.map((g) => g.sicherung.kopf.id));
  const jetzt = Date.now();
  return koepfe
    .filter(
      (k) => k.stuecke > 0 && !imTab.has(k.id) && istVerwaist(k, gesperrt, jetzt),
    )
    .sort((a, b) => a.begonnen - b.begonnen);
}

/**
 * Setzt den Ton aus den Stücken zusammen. Über einen Cursor und in
 * Zwischen-Blobs, nicht mit `getAll`: sonst lägen 90 MB als ArrayBuffer
 * und noch einmal als Blob gleichzeitig im Speicher eines Telefons.
 */
async function tonAusSpeicher(kopf: AufnahmeKopf): Promise<Blob> {
  const teile: Blob[] = [];
  let puffer: ArrayBuffer[] = [];
  const tx = (await db()).transaction("stuecke");
  for (
    let cursor = await tx.store.openCursor(alleStuecke(kopf.id));
    cursor;
    cursor = await cursor.continue()
  ) {
    puffer.push(cursor.value.daten);
    if (puffer.length >= 60) {
      teile.push(new Blob(puffer));
      puffer = [];
    }
  }
  if (puffer.length) teile.push(new Blob(puffer));
  return new Blob(teile, { type: kopf.mimeType });
}

export async function verwerfen(id: string): Promise<void> {
  const d = await db();
  const tx = d.transaction(["koepfe", "stuecke"], "readwrite");
  await Promise.all([
    tx.objectStore("koepfe").delete(id),
    tx.objectStore("stuecke").delete(alleStuecke(id)),
    tx.done,
  ]);
  melden();
}

/**
 * Sendet eine Aufnahme an die Box und löscht die Sicherung erst nach der
 * Bestätigung. `ton` ist der Inhalt aus dem Arbeitsspeicher, falls der
 * Tab ihn noch hat; sonst kommt er aus IndexedDB.
 */
export async function senden(
  kopf: AufnahmeKopf,
  ton?: Blob,
  beiFortschritt?: (f: Fortschritt) => void,
): Promise<MeetingDto> {
  const besprechung = await createMeeting({
    blob: ton ?? (await tonAusSpeicher(kopf)),
    title: kopf.titel,
    // Mit dem Ton aus dem Arbeitsspeicher gilt die gemessene Dauer, auch
    // wenn IndexedDB nur einen Teil hat.
    durationMs: ton && kopf.dauerMs !== null ? kopf.dauerMs : dauerVon(kopf),
    mimeType: kopf.mimeType,
    templateId: kopf.templateId,
    audioLanguage: kopf.audioLanguage,
    quickMode: kopf.quickMode,
    beiFortschritt,
  });
  try {
    await verwerfen(kopf.id);
  } catch {
    // Die Besprechung ist angelegt; eine liegen gebliebene Sicherung ist
    // lästig, aber kein Verlust. Sie wird beim nächsten Mal angeboten.
  }
  return besprechung;
}

/**
 * Wie `senden`, aber für eine Aufnahme aus einem anderen Tab oder einer
 * früheren Sitzung: erst die Sperre, damit zwei Tabs sie nicht doppelt
 * anlegen. `null` heißt, jemand anderes hat sie gerade.
 */
export async function sendenMitSperre(
  kopf: AufnahmeKopf,
  beiFortschritt?: (f: Fortschritt) => void,
): Promise<MeetingDto | null> {
  const lm = locks();
  if (!lm) return senden(kopf, undefined, beiFortschritt);
  try {
    return await lm.request(
      SPERRE + kopf.id,
      { ifAvailable: true },
      async (sperre) => (sperre ? senden(kopf, undefined, beiFortschritt) : null),
    );
  } finally {
    // Die Sperre ist jetzt frei. Solange sie hielt, hat jede Liste diese
    // Aufnahme ausgeblendet — scheiterte das Senden, soll sie sofort
    // zurückkommen, nicht erst beim nächsten Seitenwechsel.
    melden();
  }
}

/** Legt die Aufnahme als Datei in den Download-Ordner des Geräts. */
export async function alsDateiSpeichern(
  kopf: AufnahmeKopf,
  ton?: Blob,
): Promise<void> {
  const datei = ton ?? (await tonAusSpeicher(kopf));
  const url = URL.createObjectURL(datei);
  const a = document.createElement("a");
  a.href = url;
  a.download = dateinameVon(kopf);
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Safari bricht den Download ab, wenn die Adresse sofort verschwindet.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
