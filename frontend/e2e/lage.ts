// Aus Rockets frontend/e2e/lage.ts, eine Ausnahme für Insilo (Kartenfuß).
//
// Wo Dinge auf der Seite stehen — geprüft, was die GUI-Prüfung vom 30.9.2026
// übersah: ein Hinweis ohne Seitenrand, bündig an der Navigation und ohne
// Abstand an die Reiter geklebt (Einstellungen, nur ohne Passwort sichtbar).
// Läuft im Browser über page.evaluate, deshalb ohne Importe.

export function lagePruefen(): string[] {
  const funde: string[] = [];
  const main = document.querySelector("main");
  if (!main) return funde;
  const m = main.getBoundingClientRect();
  const RAND = 12;
  const name = (e: Element) => {
    const k = String((e as HTMLElement).className || "").split(" ").filter(Boolean)[0];
    return `${e.tagName.toLowerCase()}${k ? "." + k : ""}`;
  };
  const sichtbar = (e: Element) => {
    const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
  };

  // 1. Text, der am Rand des Inhalts klebt.
  for (const e of main.querySelectorAll("*")) {
    if (!sichtbar(e)) continue;
    const eigenerText = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent!.trim());
    if (!eigenerText) continue;
    // Was in einem rollenden Bereich steht (Board, breite Tabellen), darf
    // über den Rand hinaus — dafür rollt er. Nur für Vorleser: unsichtbar.
    if (e.closest(".nur-vorleser")) continue;
    let rollt = false;
    for (let a = e.parentElement; a && a !== main; a = a.parentElement) {
      const ox = getComputedStyle(a).overflowX;
      if (ox === "auto" || ox === "scroll" || ox === "hidden") { rollt = true; break; }
    }
    if (rollt) continue;
    const r = e.getBoundingClientRect();
    if (r.left < m.left + RAND || r.right > m.right - RAND + 1) {
      funde.push(`am Rand: ${name(e)} „${e.textContent!.trim().slice(0, 30)}“`);
    }
  }

  // 2. Kästen mit Rand oder Fläche, die ohne Abstand am Vorgänger kleben.
  const kasten = (e: Element) => {
    const s = getComputedStyle(e);
    return parseFloat(s.borderTopWidth) > 0 || (s.backgroundColor !== "rgba(0, 0, 0, 0)" && s.backgroundColor !== "transparent");
  };
  const geschwister = [...main.querySelectorAll("*")].filter((e) => e.parentElement && sichtbar(e) && getComputedStyle(e).position === "static");
  for (const e of geschwister) {
    const vor = e.previousElementSibling;
    if (!vor || !sichtbar(vor) || !kasten(e)) continue;
    const s = getComputedStyle(e.parentElement!);
    if (s.display === "flex" && s.flexDirection.startsWith("row")) continue;
    if (s.display === "grid" || s.display === "inline-flex" || s.display === "table-row") continue;
    if (s.display.startsWith("table")) continue;
    // Zeilen einer Liste stoßen gewollt aneinander, getrennt durch ihren Rand.
    if (e.parentElement!.tagName === "UL" || e.parentElement!.tagName === "OL") continue;
    // Insilo: Der Fuß einer Karte (nur Oberkante, im umrandeten Kasten)
    // schließt gewollt bündig an — die Linie ist der Abstand. Sonst gleich
    // wie Rockets e2e/lage.ts.
    const es = getComputedStyle(e);
    const nurOben = parseFloat(es.borderTopWidth) > 0 && parseFloat(es.borderLeftWidth) === 0 && parseFloat(es.borderBottomWidth) === 0;
    if (nurOben && parseFloat(s.borderTopWidth) > 0 && parseFloat(s.borderLeftWidth) > 0) continue;
    const abstand = e.getBoundingClientRect().top - vor.getBoundingClientRect().bottom;
    if (abstand >= -1 && abstand < 4 && !kasten(vor)) {
      funde.push(`ohne Abstand: ${name(e)} unter ${name(vor)}`);
    }
  }
  // 3. Zeichen im Leerzustand mittig über dem Text.
  for (const leer of main.querySelectorAll(".leerzustand")) {
    const zeichen = leer.querySelector(":scope > svg");
    if (!zeichen || !sichtbar(zeichen)) continue;
    const a = leer.getBoundingClientRect();
    const z = zeichen.getBoundingClientRect();
    if (Math.abs(z.left + z.width / 2 - (a.left + a.width / 2)) > 2) {
      funde.push("Leerzustand: Zeichen nicht mittig");
    }
  }
  return [...new Set(funde)];
}
