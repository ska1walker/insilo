import { defineConfig, devices } from "@playwright/test";

// Der Rundgang im Browser, nach Rockets e2e/ (CI-Anschluss, Etappe 7). Er
// erwartet eine laufende App mit Beispieldaten (e2e/beispiel/) — in der CI
// baut der Job „oberfläche“ sie auf, lokal genügt `npm run e2e` gegen einen
// gestarteten Stand.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "e2e-bericht" }]],
  globalSetup: "./e2e/vorbereitung.ts",
  use: {
    baseURL: process.env.INSILO_URL ?? "http://localhost:3020",
    screenshot: "only-on-failure",
    locale: "de-DE",
    timezoneId: "Europe/Berlin",
    // Was Authelia vor dem Pod nach oben reicht; middleware.ts macht daraus
    // X-Bfl-User — auch für <audio src>, das keinen eigenen Header setzt.
    extraHTTPHeaders: { "Remote-User": process.env.INSILO_USER ?? "devuser" },
    // Auf Rechnern mit vorinstalliertem Chromium (Claude-Sitzungen) liegt es
    // dort; in der CI installiert der Job den passenden Browser selbst.
    launchOptions: process.env.INSILO_CHROMIUM ? { executablePath: process.env.INSILO_CHROMIUM } : {},
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1400, height: 900 } } },
    { name: "handy", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } } },
  ],
});
