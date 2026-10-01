"use client";

// Baustein HB-DIALOG aus dem AImighty-CI, Code aus Rocket (components/dialogfalle.ts).

// Was jeder Dialog können muss und keiner konnte: Der Fokus geht beim
// Öffnen hinein, Tab bleibt drin, Escape schließt, und danach steht der
// Fokus wieder dort, wo er vorher war. Ohne das landete, wer mit der
// Tastatur arbeitet, nach dem Öffnen auf der Seite dahinter.
//
// Als Ref-Rückruf statt als Effekt, damit es auch für Dialoge gilt, die
// nur bedingt erscheinen (Löschen bestätigen): Er läuft, wenn das Element
// kommt, und räumt auf, wenn es geht (React 19).

import { useCallback, useRef } from "react";

const FOKUSSIERBAR =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function ziele(el: HTMLElement): HTMLElement[] {
  return [...el.querySelectorAll<HTMLElement>(FOKUSSIERBAR)].filter((e) => e.getClientRects().length > 0);
}

export function useDialogfalle(schliessen: () => void) {
  const zu = useRef(schliessen);
  zu.current = schliessen;

  return useCallback((el: HTMLElement | null) => {
    if (!el) return;
    const vorher = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const hinein = () => {
      const alle = ziele(el);
      // Wer es sagt (data-autofokus), bekommt ihn — bei einer Rückfrage
      // „Abbrechen", damit ein Enter nichts löscht. Sonst das erste
      // Eingabefeld: dafür wurde der Dialog geöffnet.
      const erstes =
        alle.find((e) => e.hasAttribute("data-autofokus")) ??
        alle.find((e) => e.matches("input, select, textarea")) ??
        alle[0];
      erstes?.focus();
    };
    if (!el.contains(document.activeElement)) hinein();

    // Verschwindet das Feld mit dem Fokus (etwa weil der KI-Stand nachlädt
    // und die Erfassung neu zeichnet), fiele er auf die Seite dahinter.
    let zuletzt: Element | null = document.activeElement;
    const merken = (e: FocusEvent) => { zuletzt = e.target as Element; };
    el.addEventListener("focusin", merken);
    const beobachter = new MutationObserver(() => {
      if (zuletzt && !zuletzt.isConnected && !el.contains(document.activeElement)) hinein();
    });
    beobachter.observe(el, { childList: true, subtree: true });

    const taste = (e: KeyboardEvent) => {
      // Wer Escape schon für sich genutzt hat (eine offene Auswahl),
      // hat preventDefault gerufen; dann bleibt der Dialog.
      if (e.key === "Escape" && !e.defaultPrevented) {
        e.preventDefault();
        zu.current();
        return;
      }
      if (e.key !== "Tab") return;
      const alle = ziele(el);
      if (alle.length === 0) return;
      const erstes = alle[0];
      const letztes = alle[alle.length - 1];
      if (e.shiftKey && (document.activeElement === erstes || !el.contains(document.activeElement))) {
        e.preventDefault();
        letztes.focus();
      } else if (!e.shiftKey && (document.activeElement === letztes || !el.contains(document.activeElement))) {
        e.preventDefault();
        erstes.focus();
      }
    };
    el.addEventListener("keydown", taste);

    return () => {
      el.removeEventListener("keydown", taste);
      el.removeEventListener("focusin", merken);
      beobachter.disconnect();
      // Das Menü, aus dem der Dialog kam, gibt es dann meist nicht mehr.
      if (vorher?.isConnected) vorher.focus();
    };
  }, []);
}
