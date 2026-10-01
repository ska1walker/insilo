"use client";

// Nach Rockets components/tab-titel.tsx (CI HB-SEITENKOPF).
//
// Der Titel im Browser-Tab: zuerst die Seite, dann die Anwendung
// („Firmen · Rocket“). Bleiben mehrere Tabs offen, unterscheidet man sie so;
// abgeschnitten wird der Name, den das Zeichen im Tab schon sagt
// (ABGLEICH G7 im CI, medien/app.md „Im Browser-Tab“).

import { useEffect } from "react";

export const ANWENDUNG = "Insilo";

export function tabTitel(seite?: string): string {
  const s = seite?.trim();
  return s ? `${s} · ${ANWENDUNG}` : ANWENDUNG;
}

export function TabTitel({ seite }: { seite: string }) {
  useEffect(() => {
    const soll = tabTitel(seite);
    document.title = soll;
    // Next schreibt den Titel aus den Metadaten nach dem ersten Zeichnen noch
    // einmal ins <title> — ohne Wache stünde danach wieder nur „Insilo“.
    const wache = new MutationObserver(() => {
      if (document.title !== soll) document.title = soll;
    });
    wache.observe(document.head, { subtree: true, childList: true, characterData: true });
    return () => {
      wache.disconnect();
      document.title = ANWENDUNG;
    };
  }, [seite]);
  return null;
}
