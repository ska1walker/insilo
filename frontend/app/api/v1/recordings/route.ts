/**
 * Tonaufnahmen ans Backend — gestreamt, nicht gepuffert.
 *
 * **Warum es diesen Handler gibt.** Am 14.9.2026 ging eine 90-Minuten-
 * Besprechung verloren. Alle `/api/*`-Aufrufe liefen durch die Middleware,
 * und sobald Middleware läuft, puffert Next.js den Rumpf, um ihn ihr
 * anbieten zu können — und schneidet ihn bei
 * `experimental.middlewareClientMaxBodySize` ab, Vorgabe 10 MB. In
 * `node_modules/next/dist/server/body-streams.js` beendet Next dann
 * **beide** Datenströme, auch den, der danach ans Backend geht. Das
 * Backend bekam die ersten 10 MB von rund 90, lehnte den abgeschnittenen
 * Multipart-Rumpf mit 400 ab, und die Besprechung wurde nie angelegt.
 *
 * **Warum nicht einfach die Grenze heben.** Gemessen am 14.9.2026, lokal
 * mit `next start` gegen ein künstlich langsames Backend, 500-MB-Upload:
 * mit `middlewareClientMaxBodySize: "500mb"` wuchs der Prozess um 464 MB
 * und blieb zehn Sekunden danach bei 480 MB. Die Anfrage scheiterte
 * trotzdem mit 500, weil der Multipart-Rahmen die Datei ein paar hundert
 * Bytes über die Grenze hob — die Kante wandert nur. Der Frontend-Pod hat
 * 1 GiB.
 *
 * **Was hier passiert.** Die Middleware lässt diesen Pfad aus (siehe
 * `matcher` in `middleware.ts`), damit wird nichts geklont. Der Rumpf geht
 * als Datenstrom weiter, und der Datenstrom bremst den Browser auf das
 * Tempo des Backends. Derselbe Upload kam vollständig an (201), der
 * Prozess wuchs um 277 MB und fiel danach auf den Ausgangswert zurück;
 * gegen ein schnelles Backend waren es 507 MB Spitze, ebenfalls wieder
 * freigegeben. Das ist nicht „nur ein Stück im Speicher" — Node puffert
 * großzügig, solange der Speicher frei ist —, aber es bleibt nichts liegen
 * und es gibt keine feste Grenze. Eine 90-Minuten-Aufnahme hat rund 90 MB.
 * Die Kopfzeilen kommen aus derselben Funktion wie bei jedem anderen
 * Aufruf.
 */
import { weiterleitungsKopfzeilen } from "@/lib/weiterleitung";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Kopfzeilen, die nur für eine einzelne Verbindung gelten und nicht über
// einen Zwischenschritt hinweg weitergereicht werden dürfen (RFC 9110 §7.6.1).
//
// `expect` gehört dazu, und ohne es scheitert der Upload: große Uploads
// kündigen sich oft mit `Expect: 100-continue` an, und Nodes `fetch`
// (undici) weist jede Anfrage mit dieser Kopfzeile ab — "expect header not
// supported". Gefunden mit einem 200-MB-Upload per curl beim Messen des
// Fixes; Browser schicken sie nicht, Zwischenstationen können es.
const NUR_FUER_DIESE_VERBINDUNG = [
  "connection",
  "keep-alive",
  "proxy-connection",
  "transfer-encoding",
  "upgrade",
  "host",
  "expect",
  "te",
  "trailer",
];

function backend(): string {
  return process.env.INSILO_BACKEND_INTERNAL ?? "http://insilo-backend:8000";
}

export async function POST(request: Request): Promise<Response> {
  const kopfzeilen = weiterleitungsKopfzeilen(request.headers);
  for (const name of NUR_FUER_DIESE_VERBINDUNG) kopfzeilen.delete(name);

  let antwort: Response;
  try {
    antwort = await fetch(`${backend()}/api/v1/recordings`, {
      method: "POST",
      headers: kopfzeilen,
      body: request.body,
      // Node verlangt das für einen Rumpf, der als Datenstrom kommt.
      // @ts-expect-error — `duplex` fehlt in den DOM-Typen, Node kennt es.
      duplex: "half",
      cache: "no-store",
    });
  } catch (fehler) {
    console.error("recordings: backend unreachable", fehler);
    return Response.json(
      { detail: "Backend nicht erreichbar." },
      { status: 502 },
    );
  }

  // `fetch` hat einen komprimierten Rumpf bereits entpackt; die Angaben
  // dazu würden den Browser ein zweites Mal entpacken lassen.
  const zurueck = new Headers(antwort.headers);
  for (const name of [...NUR_FUER_DIESE_VERBINDUNG, "content-encoding", "content-length"]) {
    zurueck.delete(name);
  }
  return new Response(antwort.body, { status: antwort.status, headers: zurueck });
}
