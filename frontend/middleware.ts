import { NextResponse, type NextRequest } from "next/server";

/**
 * Hängt das gemeinsame Geheimnis an jeden Aufruf, den der Next.js-Server
 * an das Backend weiterreicht.
 *
 * **Warum hier und nicht im Browser:** `INSILO_INTERNAL_TOKEN` trägt kein
 * `NEXT_PUBLIC_`-Präfix und ist damit ausschließlich serverseitig
 * lesbar. Die Middleware läuft im Pod, nicht im Browser — das Geheimnis
 * kommt nie in ein Bundle und nie in die Entwicklerwerkzeuge.
 *
 * **Warum Middleware und nicht ein eigener Proxy-Endpunkt:** die
 * Weiterleitung in `next.config.mjs` streamt. Ein Route Handler müsste
 * den Rumpf selbst durchreichen — bei Tonaufnahmen bis 500 MB ist das
 * der Unterschied zwischen Durchreichen und Zwischenspeichern.
 *
 * **Was mitgeschickt wird, wird vorher entfernt.** Ein Browser könnte
 * `X-Insilo-Internal` selbst setzen und so einen erratenen Wert
 * einschleusen; `set` überschreibt ihn. Steht kein Geheimnis in der
 * Umgebung, wird die Kopfzeile gelöscht statt leer gesetzt — dann
 * entscheidet allein das Backend, ob es ohne Torwächter läuft.
 */
export function middleware(request: NextRequest) {
  const kopfzeilen = new Headers(request.headers);
  const geheimnis = process.env.INSILO_INTERNAL_TOKEN;

  if (geheimnis) {
    kopfzeilen.set("X-Insilo-Internal", geheimnis);
  } else {
    kopfzeilen.delete("X-Insilo-Internal");
  }

  // Die Identität aus der Hand von Authelia nehmen, wo es geht.
  //
  // Am 5.9. an der Box nachgemessen: der Envoy-Sidecar setzt
  // `X-Bfl-User` **nicht**. Die Kopfzeile kommt heute aus dem Browser
  // (`lib/api/client.ts`) — sie wegzulassen hieße, dass niemand mehr
  // hineinkommt.
  //
  // Was Authelia bei erfolgreicher Prüfung nach oben durchreichen darf,
  // steht dagegen fest in Envoys `allowed_upstream_headers`: alles mit
  // dem Präfix `remote-`. Das ist Authelias übliche Auskunft über den
  // angemeldeten Nutzer. Ist sie da, gewinnt sie — und der Browser kann
  // dann keine fremde Identität mehr behaupten, weil sein Wert hier
  // überschrieben wird.
  //
  // Fehlt sie, bleibt es beim bisherigen Verhalten. Das ist bewusst kein
  // Fehlerfall: ob Authelia sie in dieser Aufstellung tatsächlich
  // schickt, war ohne angemeldete Sitzung nicht zu prüfen. So ist die
  // Absicherung wirksam, sobald sie kommt, und bricht nichts, falls
  // nicht.
  const vonAuthelia = request.headers.get("Remote-User");
  if (vonAuthelia) {
    kopfzeilen.set("X-Bfl-User", vonAuthelia);
  }

  return NextResponse.next({ request: { headers: kopfzeilen } });
}

export const config = {
  // Nur die weitergereichten Aufrufe. `/api/health` ist die eigene Route
  // des Frontends und braucht nichts davon, schadet aber auch nicht.
  matcher: "/api/:path*",
};
