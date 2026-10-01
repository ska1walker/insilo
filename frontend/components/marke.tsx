// Baustein HB-MARKE aus dem AImighty-CI (bauteile/HB-MARKE.md), Code aus
// Rocket (components/marke.tsx).

/**
 * Die Wortmarke von AImighty in der Kopfecke.
 *
 * Zwei Dateien statt einer umgefärbten: Beide tragen dasselbe goldene
 * Wappen, nur „mighty" wechselt zwischen Dunkelblau und Weiß. Welche gilt,
 * entscheidet das CSS an der Klasse `dunkel` — so ist kein Skript nötig, und
 * beim ersten Bild steht schon die richtige da. Die Dateien kommen
 * unverändert aus dem CI (`public/marke/README.md`).
 */
export function Marke() {
  return (
    <span className="marke-logo">
      {/* eslint-disable-next-line @next/next/no-img-element -- SVG, fest 28 px, kein Bildoptimierer nötig */}
      <img src="/marke/aimighty-hell.svg" alt="AImighty" width={472} height={167} className="marke-logo-bild hell" />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/marke/aimighty-dunkel.svg" alt="" aria-hidden="true" width={472} height={167} className="marke-logo-bild dunkel" />
    </span>
  );
}
