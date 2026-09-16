/**
 * Wie oft die Besprechungsansicht nachfragt, während verarbeitet wird.
 *
 * Bisher: alle zwei Sekunden, unbegrenzt. Das war vertretbar, solange die
 * Verarbeitung nach spätestens dreißig Minuten endete — Celery brach sie
 * dort ab. Seit 0.1.99 darf sie bis zu vier Stunden laufen (der Grund
 * steht in `backend/app/verarbeitungszeit.py`), und ein offen gelassener
 * Tab käme auf über siebentausend Abfragen.
 *
 * Die Staffelung hält den Anfang schnell — eine kurze Notiz ist in
 * Sekunden fertig, und dafür soll die Ansicht sofort umspringen — und
 * wird gemächlich, je länger es dauert. Wer eine Stunde wartet, merkt
 * dreißig Sekunden Verzögerung nicht.
 */

/** Abstand bis zur nächsten Abfrage, nach bisheriger Wartezeit. */
export function pollAbstandMs(seitMs: number): number {
  if (seitMs < 30_000) return 2_000;
  if (seitMs < 5 * 60_000) return 5_000;
  if (seitMs < 20 * 60_000) return 15_000;
  return 30_000;
}

/** Wie viele Abfragen eine Verarbeitung dieser Länge kostet. */
export function pollAnzahl(dauerMs: number): number {
  let verstrichen = 0;
  let anzahl = 0;
  while (verstrichen < dauerMs) {
    verstrichen += pollAbstandMs(verstrichen);
    anzahl += 1;
  }
  return anzahl;
}
