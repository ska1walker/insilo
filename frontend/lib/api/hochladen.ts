/**
 * Hochladen mit Fortschritt.
 *
 * `fetch` meldet nicht, wie viel eines Rumpfs schon gesendet ist. Beim
 * Vorfall vom 14.9.2026 stand eine Aufnahme von 90 MB minutenlang unter
 * „Wird gespeichert", ohne dass jemand sehen konnte, ob sich etwas bewegt.
 * `XMLHttpRequest` kann es. Alles andere macht dieser Weg wie
 * `apiRequest`: dieselbe Adresse, dieselben Kopfzeilen, `ApiError` bei einer
 * Antwort außerhalb von 2xx — und bei einem Netzfehler ausdrücklich **kein**
 * `ApiError`, damit die Oberfläche „Box nicht erreichbar" von „Box hat
 * abgelehnt" unterscheiden kann.
 */
import { API_BASE, ApiError, anfrageKopfzeilen } from "./client";

export type Fortschritt = { geladen: number; gesamt: number };

type XhrArtig = Pick<
  XMLHttpRequest,
  "open" | "setRequestHeader" | "send" | "status" | "statusText" | "responseText"
> & {
  upload: { onprogress: ((e: ProgressEvent) => void) | null };
  onload: (() => void) | null;
  onerror: (() => void) | null;
  ontimeout: (() => void) | null;
  onabort: (() => void) | null;
  getResponseHeader(name: string): string | null;
};

export function hochladen<T>(
  pfad: string,
  form: FormData,
  optionen: {
    beiFortschritt?: (f: Fortschritt) => void;
    xhrFabrik?: () => XhrArtig;
    cookie?: string | null;
  } = {},
): Promise<T> {
  const xhr = optionen.xhrFabrik
    ? optionen.xhrFabrik()
    : (new XMLHttpRequest() as unknown as XhrArtig);
  const cookie =
    optionen.cookie !== undefined
      ? optionen.cookie
      : typeof document === "undefined"
        ? null
        : document.cookie;

  return new Promise<T>((erfuellt, abgelehnt) => {
    xhr.open("POST", `${API_BASE}${pfad}`);
    for (const [name, wert] of Object.entries(anfrageKopfzeilen(cookie))) {
      xhr.setRequestHeader(name, wert);
    }

    // Auf ganze Prozent gedrosselt: der Browser meldet oft Dutzende Male
    // pro Sekunde, und jede Meldung ist ein neues Rendern.
    let zuletzt = -1;
    xhr.upload.onprogress = (e) => {
      if (!optionen.beiFortschritt || !e.lengthComputable || e.total <= 0) return;
      const prozent = Math.floor((e.loaded / e.total) * 100);
      if (prozent === zuletzt) return;
      zuletzt = prozent;
      optionen.beiFortschritt({ geladen: e.loaded, gesamt: e.total });
    };

    xhr.onload = () => {
      let geparst: unknown = null;
      const typ = xhr.getResponseHeader("content-type") ?? "";
      if (typ.includes("application/json") && xhr.responseText) {
        try {
          geparst = JSON.parse(xhr.responseText);
        } catch {
          /* ignore */
        }
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        erfuellt((geparst ?? xhr.responseText) as T);
      } else {
        abgelehnt(
          new ApiError(xhr.status, `${xhr.status} ${xhr.statusText}`, geparst),
        );
      }
    };
    const netzfehler = (was: string) => () =>
      abgelehnt(new Error(`upload ${was}`));
    xhr.onerror = netzfehler("failed");
    xhr.ontimeout = netzfehler("timed out");
    xhr.onabort = netzfehler("aborted");

    xhr.send(form);
  });
}
