"use client";

// Baustein HB-DIALOG aus dem AImighty-CI (bauteile/HB-DIALOG.md), Code aus
// Rocket (components/dialog.tsx). Insilo braucht vorerst nur die Rückfrage:
// Sie ersetzt das Browser-`confirm()`, das weder gestaltet noch übersetzt
// werden kann (ABGLEICH IN-R2). Der bestätigende Knopf ist rot und nennt
// das Objekt („Sprecher löschen“), Abbrechen bekommt zuerst den Fokus,
// damit ein Enter nichts löscht.

import { useTranslations } from "next-intl";
import { useDialogfalle } from "@/components/dialogfalle";

export function Rueckfrage({
  titel,
  label,
  text,
  beiSchliessen,
  knopf,
  vorsicht = true,
  children,
}: {
  titel: React.ReactNode;
  label: string;
  /** Der Satz unter dem Titel — was geschieht, wenn man bestätigt. */
  text?: React.ReactNode;
  beiSchliessen: () => void;
  /** Der bestätigende Knopf, fertig gebaut (mit Zustand „läuft"). */
  knopf: React.ReactNode;
  vorsicht?: boolean;
  /** Felder zwischen Satz und Knöpfen, etwa ein Ziel oder ein Grund. */
  children?: React.ReactNode;
}) {
  const t = useTranslations("common");
  const falle = useDialogfalle(beiSchliessen);
  return (
    <div className="dialog-schicht" role="dialog" aria-modal="true" aria-label={label} ref={falle}>
      <div className="karte rueckfrage">
        <h2>{titel}</h2>
        {text && <p className="rueckfrage-text">{text}</p>}
        {children}
        <div className="btn-reihe">
          {knopf}
          <button type="button" className="btn btn-still" data-autofokus={vorsicht ? "" : undefined} onClick={beiSchliessen}>
            {t("cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
