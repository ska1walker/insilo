// Baustein HB-SYMBOL aus dem AImighty-CI (bauteile/HB-SYMBOL.md), Code aus
// Rocket (components/symbol.tsx).
//
// Der Rumpf jedes Zeichens. Insilo zeichnet nur aus dem CI-Set
// (aimighty-ci, marke/icons/ui/, Kopie unter ci/), die Zeichen selbst stehen
// in lib/symbole.tsx (erzeugt). Vorher lucide-react direkt.
//
// Zwei Regeln aus dem CI (kern/icons.md, ABGLEICH.md R2):
// - Größen nur 16 · 20 · 24, dazu 40 im Leerzustand. Der Typ lässt keine
//   andere zu.
// - Strich 1,5 px bei jeder Größe. Im 24er-Raster also 1,5 × 24 / Größe —
//   ein Zeichen, das mit der Größe dicker wird, steht neben Text zu fett.
//
// Eine Ausnahme, eingetragen in medien/app.md (ABGLEICH IN-Z2): das Zeichen
// im runden Aufnahmeknopf, der einen großen Hauptaktion: 36 px im 120-px-
// Knopf auf Start und /aufnahme, 80 und 96 px im großen Knopf auf /idee.
// Auch dort bleibt der Strich 1,5 px.

import type { ReactNode, SVGProps } from "react";

export type Symbolgroesse = 16 | 20 | 24 | 40;

/** Nur für den runden Aufnahmeknopf (IN-Z2). */
export type Aufnahmegroesse = 36 | 80 | 96;

export type SymbolProps = Omit<SVGProps<SVGSVGElement>, "children" | "strokeWidth" | "width" | "height"> & {
  size?: Symbolgroesse;
};

export type SymbolKomponente = ((props: SymbolProps) => ReactNode) & { displayName?: string };

export function strich(groesse: number): number {
  return (1.5 * 24) / groesse;
}

function rumpf(name: string, kinder: ReactNode, size: number, rest: Omit<SymbolProps, "size">) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strich(size)}
      strokeLinecap="round"
      strokeLinejoin="round"
      data-symbol={name}
      {...rest}
    >
      {kinder}
    </svg>
  );
}

const KINDER = new Map<SymbolKomponente, { name: string; kinder: ReactNode }>();

export function symbol(name: string, kinder: ReactNode): SymbolKomponente {
  function Zeichen({ size = 16, ...rest }: SymbolProps) {
    return rumpf(name, kinder, size, rest);
  }
  Zeichen.displayName = `Symbol(${name})`;
  KINDER.set(Zeichen, { name, kinder });
  return Zeichen;
}

/** Ein Zeichen in der Größe des Aufnahmeknopfs (IN-Z2), Strich 1,5 px. */
export function Aufnahmezeichen({
  zeichen,
  size,
  ...rest
}: Omit<SymbolProps, "size"> & { zeichen: SymbolKomponente; size: Aufnahmegroesse }) {
  const z = KINDER.get(zeichen);
  if (!z) throw new Error("Aufnahmezeichen: kein Zeichen aus lib/symbole.tsx");
  return rumpf(z.name, z.kinder, size, { ...rest, "data-aufnahme": "" } as Omit<SymbolProps, "size">);
}
