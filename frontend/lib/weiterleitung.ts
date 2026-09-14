/**
 * Die Kopfzeilen für einen Aufruf, den das Frontend ans Backend weiterreicht.
 *
 * **Eine Stelle für zwei Wege.** Gewöhnliche Aufrufe gehen durch die
 * Middleware (`middleware.ts`), Tonaufnahmen durch einen eigenen Route
 * Handler (`app/api/v1/recordings/route.ts`), der den Rumpf streamt. Beide
 * müssen dasselbe Geheimnis anhängen und dieselbe Identität setzen — stünde
 * das zweimal im Code, liefe es beim nächsten Umbau auseinander, und der
 * Upload wäre der Weg, auf dem man sich als jemand anderes ausgeben kann.
 *
 * `INSILO_INTERNAL_TOKEN` trägt kein `NEXT_PUBLIC_`-Präfix und ist damit
 * ausschließlich serverseitig lesbar. Ein vom Browser mitgeschicktes
 * `X-Insilo-Internal` wird überschrieben oder gelöscht, nie durchgereicht.
 */
export function weiterleitungsKopfzeilen(eingang: Headers): Headers {
  const kopfzeilen = new Headers(eingang);
  const geheimnis = process.env.INSILO_INTERNAL_TOKEN;

  if (geheimnis) {
    kopfzeilen.set("X-Insilo-Internal", geheimnis);
  } else {
    kopfzeilen.delete("X-Insilo-Internal");
  }

  // Die Identität aus der Hand von Authelia nehmen, wo es geht. Der
  // Envoy-Sidecar setzt `X-Bfl-User` nicht selbst (am 5.9. an der Box
  // nachgemessen); was Authelia nach oben durchreichen darf, trägt das
  // Präfix `remote-`. Ist es da, gewinnt es, und der Browser kann keine
  // fremde Identität mehr behaupten.
  const vonAuthelia = eingang.get("Remote-User");
  if (vonAuthelia) {
    kopfzeilen.set("X-Bfl-User", vonAuthelia);
  }

  return kopfzeilen;
}
