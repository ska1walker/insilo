/**
 * Tonaufnahmen ans Backend — gestreamt, mit Gegendruck, ohne `fetch`.
 *
 * **Warum es diesen Handler gibt.** Am 14.9.2026 ging eine 90-Minuten-
 * Besprechung verloren. Alle `/api/*`-Aufrufe liefen durch die Middleware,
 * und sobald Middleware läuft, puffert Next.js den Rumpf, um ihn ihr
 * anbieten zu können — und schneidet ihn bei
 * `experimental.middlewareClientMaxBodySize` ab, Vorgabe 10 MB. In
 * `node_modules/next/dist/server/body-streams.js` beendet Next dann
 * **beide** Datenströme, auch den, der danach ans Backend geht. Die
 * Middleware lässt diesen Pfad deshalb aus (siehe `matcher` in
 * `middleware.ts`). Die Weiterleitung aus `next.config.mjs` reicht den
 * Rumpf über denselben Klon weiter (`router-server.js`, `cloneBodyStream`)
 * und kommt ebenfalls nicht in Frage.
 *
 * **Warum nicht einfach die Grenze heben.** Gemessen am 14.9.2026: mit
 * `middlewareClientMaxBodySize: "500mb"` scheiterte ein 500-MB-Upload
 * trotzdem (der Multipart-Rahmen hob ihn über die Grenze), und 480 MB
 * blieben belegt.
 *
 * **Warum `http.request` und nicht `fetch`.** 0.1.96 reichte den Rumpf mit
 * `fetch` weiter. Das kam vollständig an, aber auf Kais Box stand der
 * Frontend-Prozess nach einem 600-MB-Upload bei 798 MB (Pod-Limit 1 GiB)
 * und gab den Speicher erst eine Minute später frei — zwei große Uploads
 * gleichzeitig hätten den Pod reißen können. Gemessen am 15.9.2026, ohne
 * Next, 500 MB gegen eine schnelle Senke, Zuwachs des Prozesses:
 *
 *   Web-Datenstrom → `fetch`                         457–526 MB
 *   Web-Datenstrom → `Readable.fromWeb` → `pipeline`   80 MB
 *   Node-Datenstrom → `pipeline` (ohne Next)            57–85 MB
 *
 * Es liegt also nicht am Web-Datenstrom, den Next dem Handler gibt, sondern
 * an `fetch` auf der ausgehenden Seite. Die Kopfzeilen kommen aus derselben
 * Funktion wie bei jedem anderen Aufruf (`lib/weiterleitung.ts`).
 */
import http from "node:http";
import https from "node:https";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import type { ReadableStream as NodeReadableStream } from "node:stream/web";
import {
  NUR_FUER_DIESE_VERBINDUNG,
  kopfzeilenFuersBackend,
} from "@/lib/weiterleitung";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function backend(): URL {
  return new URL(
    "/api/v1/recordings",
    process.env.INSILO_BACKEND_INTERNAL ?? "http://insilo-backend:8000",
  );
}

const nichtErreichbar = () =>
  Response.json({ detail: "Backend nicht erreichbar." }, { status: 502 });

export async function POST(request: Request): Promise<Response> {
  const ziel = backend();
  const modul = ziel.protocol === "https:" ? https : http;
  const weiter = modul.request(ziel, {
    method: "POST",
    headers: kopfzeilenFuersBackend(request.headers),
  });
  // Fehler landen über `antwort` und `pipeline` beim Aufrufer. Ohne diesen
  // Listener beendete ein zweiter Socket-Fehler nach der Antwort den ganzen
  // Frontend-Prozess.
  weiter.on("error", () => {});
  // Ruht die Verbindung zum Backend zehn Minuten lang (weder Bytes hin
  // noch zurück), gilt es als nicht erreichbar. `fetch` brachte dafür eigene
  // Grenzen mit; `http.request` hat keine. Eine Wiederholung ist seit 0.1.98
  // unschädlich — die Box erkennt die Aufnahme an ihrer Kennung.
  const ruheMs = Number(process.env.INSILO_BACKEND_TIMEOUT_MS) || 10 * 60 * 1000;
  weiter.setTimeout(ruheMs, () => weiter.destroy(new Error("backend idle timeout")));

  // Das Backend liest das ganze Formular, bevor es antwortet — auch ein 413
  // kommt erst danach (auf der Box gemessen). Bricht die Verbindung vorher
  // ab, ist „nicht erreichbar" die richtige Auskunft.
  const antwort = new Promise<http.IncomingMessage>((erfuellt, abgelehnt) => {
    weiter.once("response", erfuellt);
    weiter.once("close", () => abgelehnt(new Error("closed without response")));
  });

  // `pipeline` hält den Browser an, wenn das Backend nicht nachkommt, und
  // bricht die Anfrage ans Backend ab, wenn der Browser abbricht.
  const quelle = request.body
    ? Readable.fromWeb(request.body as unknown as NodeReadableStream<Uint8Array>)
    : Readable.from([]);
  const gesendet = pipeline(quelle, weiter).then(
    () => null,
    (fehler: unknown) => fehler,
  );

  let rueck: http.IncomingMessage;
  try {
    rueck = await antwort;
  } catch (fehler) {
    console.error("recordings: backend unreachable", (await gesendet) ?? fehler);
    return nichtErreichbar();
  }

  const kopfzeilen = new Headers();
  for (const [name, wert] of Object.entries(rueck.headers)) {
    if (wert === undefined || NUR_FUER_DIESE_VERBINDUNG.includes(name)) continue;
    kopfzeilen.set(name, Array.isArray(wert) ? wert.join(", ") : wert);
  }
  // Die Antwort ist klein (die angelegte Besprechung als JSON); ganz lesen,
  // damit ein Abbruch des Backends mitten in der Antwort nicht als halber
  // Rumpf beim Browser ankommt.
  let inhalt: Buffer;
  try {
    const teile: Buffer[] = [];
    for await (const teil of rueck) teile.push(teil as Buffer);
    inhalt = Buffer.concat(teile);
  } catch (fehler) {
    console.error("recordings: backend answer broke off", fehler);
    return nichtErreichbar();
  }
  kopfzeilen.set("content-length", String(inhalt.length));
  return new Response(new Uint8Array(inhalt), {
    status: rueck.statusCode ?? 502,
    headers: kopfzeilen,
  });
}
