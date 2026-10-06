// Das Profil oben rechts (CI HB-KONTO, ABGLEICH G8, Kai 6.10.2026): ganz
// rechts in der Kopfleiste, am Desktop und am Handy an derselben Stelle wie
// in Rocket. Im Menü Einstellungen, Darstellung und Sprache — kein Abmelden,
// Olares meldet an. Escape schließt und gibt den Fokus zurück. Der Fuß der
// Navigation ist weg; Nachweis und Herkunft stehen auf „Über Insilo“.
// Einstellungen und „Über Insilo“ erreicht man nur über das Profil.

import { expect, test } from "@playwright/test";

test("Profil: ganz rechts, Menü per Tastatur, Darstellung wählbar, kein Abmelden", async ({ page, context, baseURL, isMobile }) => {
  await context.addCookies([{ name: "insilo-locale", value: "de", url: baseURL! }]);
  await page.goto("/besprechungen", { waitUntil: "networkidle" });
  const knopf = page.locator(".kopfleiste .person-knopf");
  await expect(knopf).toBeVisible();
  await expect(knopf).toHaveAttribute("aria-label", /^Konto: /);

  const lage = await page.evaluate(() => {
    const leiste = document.querySelector(".kopfleiste")!;
    return {
      profil: leiste.querySelector(".person")!.getBoundingClientRect().right,
      leiste: leiste.getBoundingClientRect().right,
    };
  });
  expect(lage.leiste - lage.profil).toBeLessThan(24);
  await expect(page.locator(".huelle-fuss")).toHaveCount(0);
  // Einstellungen und „Über“ nur im Profil, nicht in der Navigation (G8 Nachtrag).
  await expect(page.locator('.huelle-nav a[href="/einstellungen"], .huelle-nav a[href="/ueber"]')).toHaveCount(0);

  await knopf.focus();
  await page.keyboard.press("Enter");
  const menue = page.getByRole("dialog", { name: "Konto" });
  await expect(menue).toBeVisible();
  await expect(menue.getByRole("link", { name: "Einstellungen" })).toBeFocused();
  await expect(menue.getByRole("button", { name: /Abmelden/ })).toHaveCount(0);
  await expect(menue.getByRole("link", { name: "Über Insilo" })).toBeVisible();

  if (isMobile) {
    const breite = await menue.evaluate((el) => el.getBoundingClientRect().width);
    expect(breite).toBeGreaterThanOrEqual(page.viewportSize()!.width - 1);
  }

  // Darstellung aus dem Menü: dunkel wirkt sofort.
  await menue.getByRole("group", { name: "Darstellung" }).getByRole("button").nth(2).click();
  await expect(page.locator("html")).toHaveClass(/dunkel/);

  await page.keyboard.press("Escape");
  await expect(menue).toHaveCount(0);
  await expect(knopf).toBeFocused();
});

test("Über Insilo: Datenschutz-Nachweis und Herkunft", async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: "insilo-locale", value: "de", url: baseURL! }]);
  await page.goto("/ueber", { waitUntil: "networkidle" });
  await expect(page.locator("#sicherheit .nachweis")).toBeVisible();
  await expect(page.locator(".huelle-herkunft-marke")).toHaveText("AImighty");
});
