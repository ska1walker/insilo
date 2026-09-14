import { NextResponse, type NextRequest } from "next/server";
import { weiterleitungsKopfzeilen } from "@/lib/weiterleitung";

/**
 * Hängt das gemeinsame Geheimnis an jeden Aufruf, den der Next.js-Server
 * an das Backend weiterreicht, und setzt die Identität.
 *
 * Was genau gesetzt wird, steht in `lib/weiterleitung.ts` — dieselbe
 * Funktion benutzt der Route Handler für Tonaufnahmen.
 *
 * **Eine frühere Fassung dieses Kommentars war falsch.** Er behauptete,
 * die Weiterleitung aus `next.config.mjs` streame, und bei Tonaufnahmen
 * bis 500 MB sei das „der Unterschied zwischen Durchreichen und
 * Zwischenspeichern". Sobald diese Middleware auf einen Pfad passt,
 * puffert Next.js den Rumpf und schneidet ihn bei 10 MB ab. Am 14.9.2026
 * hat genau das eine 90-Minuten-Besprechung gekostet. Tonaufnahmen
 * nimmt die Middleware deshalb aus; siehe `matcher` unten und
 * `app/api/v1/recordings/route.ts`.
 */
export function middleware(request: NextRequest) {
  return NextResponse.next({
    request: { headers: weiterleitungsKopfzeilen(request.headers) },
  });
}

export const config = {
  // Alle weitergereichten Aufrufe außer genau dem Upload-Pfad. Passt die
  // Middleware auf einen Pfad, klont Next.js den Rumpf und kappt ihn bei
  // `middlewareClientMaxBodySize`. Nur dieser eine Pfad ist ausgenommen:
  // ein Unterpfad ginge sonst über die Weiterleitung ohne Geheimnis ans
  // Backend. `/api/health` ist die eigene Route des Frontends und braucht
  // nichts davon, schadet aber auch nicht.
  matcher: "/api/((?!v1/recordings$).*)",
};
