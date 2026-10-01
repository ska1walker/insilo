// Der Rundgang: jede Seite einmal, auf dem Desktop und auf dem Handy, hell
// und dunkel — nach Rockets e2e/rundgang.spec.ts (CI-Anschluss, Etappe 7).
//
// Geprüft wird, was die Bilder der Etappen 0 bis 6 als Fehler zeigten
// (CI ABGLEICH, IN-G8): eine Antwort 4xx/5xx der API, ein Skriptfehler,
// Inhalt breiter als der Bildschirm oder rechts abgeschnitten, eine Seite
// ohne oder mit zwei h1, ein Symbolknopf ohne Namen, ein Zeichen außerhalb
// 16/20/24/40 und Befunde der Stufen „critical“ und „serious“ von axe —
// einschließlich des Kontrasts.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { lagePruefen } from "./lage";

const M = (n: number) => `/m/11111111-1111-4111-8111-00000000000${n}`;

const SEITEN: [string, string][] = [
  ["Start", "/"],
  ["Aufnahme", "/aufnahme"],
  ["Besprechungen", "/besprechungen"],
  ["Besprechung fertig", M(1)],
  ["Besprechung zweite", M(2)],
  ["Besprechung läuft", M(3)],
  ["Archiv", "/archiv"],
  ["Idee", "/idee"],
  ["Einstellungen", "/einstellungen"],
  ["Datenschutz", "/datenschutz"],
  ["Papierkorb", "/papierkorb"],
  ["Protokoll", "/protokoll"],
  ["Über", "/ueber"],
];

for (const thema of ["hell", "dunkel"] as const)
for (const [name, pfad] of SEITEN) {
  test(`${name} (${pfad}) ${thema}`, async ({ page, context, baseURL }, testInfo) => {
    await context.addCookies([
      { name: "insilo-darstellung", value: thema, url: baseURL! },
      { name: "insilo-locale", value: "de", url: baseURL! },
    ]);
    const fehler: string[] = [];
    const konsole: string[] = [];
    let serverHtml = "";
    page.on("console", (m) => konsole.push(`[${m.type()}] ${m.text()}`));
    page.on("pageerror", (e) => fehler.push(`Skriptfehler: ${e.message}`));
    page.on("response", async (r) => {
      if (r.request().resourceType() === "document") serverHtml = await r.text().catch(() => "");
      if (r.url().includes("/api/") && r.status() >= 400) {
        fehler.push(`API ${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
      }
    });

    await page.goto(pfad, { waitUntil: "networkidle" });

    const lage = await page.evaluate(() => {
      // Abgeschnitten statt umgebrochen: Die Hülle hat overflow-x: hidden,
      // scrollWidth misst das nicht (IN-G8, Papierkorb bis x = 468). Deshalb
      // zusätzlich: Ragt ein sichtbares Bedienelement rechts aus dem Fenster?
      const heraus = [...document.querySelectorAll<HTMLElement>("main a, main button, main h1, main p")]
        .filter((e) => {
          const r = e.getBoundingClientRect();
          if (!(r.width > 0 && r.height > 0 && r.right > window.innerWidth + 1)) return false;
          // In einem Bereich, der rollt (die Tabelle im Protokoll), darf es
          // hinaus — dafür rollt er. Die Hülle selbst zählt nicht: ihr
          // overflow-x: hidden schneidet ab, statt zu rollen.
          for (let a = e.parentElement; a && a.tagName !== "MAIN"; a = a.parentElement) {
            const ox = getComputedStyle(a).overflowX;
            if (ox === "auto" || ox === "scroll") return false;
          }
          return true;
        })
        .map((e) => `${e.tagName.toLowerCase()} „${e.innerText.trim().slice(0, 30)}“`);
      return {
        ueberlauf: document.documentElement.scrollWidth - window.innerWidth,
        ueberschriften: document.querySelectorAll("h1").length,
        heraus: [...new Set(heraus)],
      };
    });

    const lageFunde = await page.evaluate(lagePruefen);

    // Ein Knopf, der nur ein Zeichen trägt, braucht einen Namen und einen
    // Tooltip mit demselben Wort (ABGLEICH G4 im CI, medien/app.md).
    const symbolknoepfe = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>("button, a[href], [role=button]")]
        .filter((e) => e.offsetParent && e.innerText.trim() === "")
        // Die Marke ist ein Bild mit Namen, kein Symbolknopf; der
        // Aufnahmeknopf trägt seinen Namen und bleibt eigen (G6).
        .filter((e) => e.getAttribute("role") !== "switch" && !e.closest("label") && !e.querySelector("img, [data-aufnahme]"))
        .filter((e) => !(e.getAttribute("aria-label") || e.getAttribute("aria-labelledby")) || !e.getAttribute("title"))
        .map((e) => `${e.tagName.toLowerCase()}.${String(e.className).split(" ")[0]} „${e.getAttribute("aria-label") ?? ""}“`),
    );

    // HB-SYMBOL (ABGLEICH R2): jedes sichtbare Zeichen in 16, 20, 24 oder 40,
    // der Strich gerendert 1,5 px. Ausnahme IN-Z2: das Zeichen im runden
    // Aufnahmeknopf in 36, 80 oder 96 — Strich auch dort 1,5.
    const zeichen = await page.evaluate(() =>
      [...document.querySelectorAll<SVGSVGElement>("svg[data-symbol]")]
        .filter((s) => s.getBoundingClientRect().width > 0)
        .flatMap((s) => {
          const breite = Math.round(s.getBoundingClientRect().width);
          const strich = (parseFloat(getComputedStyle(s).strokeWidth) * breite) / 24;
          const name = s.getAttribute("data-symbol");
          const erlaubt = s.hasAttribute("data-aufnahme") ? [36, 80, 96] : [16, 20, 24, 40];
          return erlaubt.includes(breite) && Math.abs(strich - 1.5) < 0.05
            ? []
            : [`${name}: ${breite} px, Strich ${strich.toFixed(2)}`];
        }),
    );

    const axe = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "best-practice"])
      .analyze();
    const schwer = axe.violations
      .filter((v) => v.impact === "critical" || v.impact === "serious")
      .map((v) => `axe ${v.id}: ${v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(" ; ")}`);

    if (fehler.length) {
      await testInfo.attach("server.html", { body: serverHtml, contentType: "text/html" });
      await testInfo.attach("dom-danach.html", { body: await page.content(), contentType: "text/html" });
      await testInfo.attach("konsole.txt", { body: konsole.join("\n"), contentType: "text/plain" });
    }

    // Die Marke `«nxt-icon»` rendert Next nur, wenn Symbole über die
    // Metadaten laufen; sie führte in Rocket zu React-Fehler #418. Insilo
    // bindet die Symbole selbst ein (app/layout.tsx).
    expect(serverHtml.includes("nxt-icon"), "Next-Marke «nxt-icon» im Server-HTML").toBe(false);
    expect(fehler, "Fehler beim Laden").toEqual([]);
    expect(lage.ueberlauf, "Seite breiter als der Bildschirm").toBeLessThanOrEqual(1);
    expect(lage.heraus, "rechts abgeschnitten").toEqual([]);
    expect(lage.ueberschriften, "genau eine h1").toBe(1);
    expect(lageFunde, "Rand, Abstand, Mitte (e2e/lage.ts)").toEqual([]);
    expect([...new Set(symbolknoepfe)], "Symbolknopf ohne Namen oder Tooltip").toEqual([]);
    expect([...new Set(zeichen)], "Zeichen außerhalb der Größen oder Strich nicht 1,5").toEqual([]);
    expect(schwer, "axe critical/serious").toEqual([]);
  });
}

// Das Symbol auf dem Home-Bildschirm und im Tab (ABGLEICH G7, R5): ohne
// Angabe baut iOS eine Kachel aus dem ersten Buchstaben des Titels.
test("Web-App-Symbole: Apple-Touch-Icon, Favicon und Manifest", async ({ page }) => {
  await page.goto("/ueber");
  const hrefs = await page.evaluate(() =>
    ["apple-touch-icon", "icon", "manifest"].map(
      (rel) => document.querySelector(`link[rel="${rel}"]`)?.getAttribute("href") ?? null,
    ),
  );
  expect(hrefs.every(Boolean), "Link-Tags im Kopf").toBe(true);
  const manifest = await (await page.request.get(hrefs[2]!)).json();
  expect(manifest.short_name).toBe("Insilo");
  for (const pfad of [hrefs[0]!, ...manifest.icons.map((i: { src: string }) => i.src)]) {
    const antwort = await page.request.get(pfad);
    expect(antwort.status(), pfad).toBe(200);
    expect(antwort.headers()["content-type"], pfad).toBe("image/png");
  }
  // Im Tab nur das Mikrofon: als SVG, das der Tableiste folgt, und als PNG
  // für Safari, das kein SVG-Favicon nimmt.
  const tab = await page.evaluate(() =>
    [...document.querySelectorAll('link[rel="icon"]')].map((l) => l.getAttribute("href")!),
  );
  const arten = [];
  for (const pfad of tab) {
    const antwort = await page.request.get(pfad);
    expect(antwort.status(), pfad).toBe(200);
    arten.push(antwort.headers()["content-type"]);
  }
  expect(arten.sort(), "Tab-Zeichen als SVG und PNG").toEqual(["image/png", "image/svg+xml"]);
});

// Der Tab nennt zuerst die Seite, dann die Anwendung (ABGLEICH G7).
test("Tab-Titel: Seite · Insilo", async ({ page }) => {
  await page.goto("/archiv", { waitUntil: "networkidle" });
  await expect(page).toHaveTitle("Archiv · Insilo");
  await page.goto("/aufnahme", { waitUntil: "networkidle" });
  await expect(page).toHaveTitle("Aufnahme · Insilo");
});
