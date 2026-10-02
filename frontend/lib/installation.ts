/**
 * Insilo als App auf dem Gerät: was der Browser gerade anbietet.
 *
 * Chrome und Edge melden mit `beforeinstallprompt`, dass sie installieren
 * können, und zwar einmal, irgendwann nach dem Laden — oft bevor jemand
 * die Einstellungen öffnet. Deshalb fängt `fangeInstallAngebot()` das
 * Ereignis früh (aus ServiceWorkerRegister) und hebt es hier auf.
 * Safari kennt das Ereignis nicht; dort bleibt nur der Weg über „Teilen".
 */

export type InstallLage =
  /** Läuft schon als App (eigenes Fenster). */
  | "installiert"
  /** Der Browser bietet die Installation an — ein Knopf genügt. */
  | "angebot"
  /** iPhone/iPad: über „Teilen → Zum Home-Bildschirm". */
  | "ios"
  /** Ohne https installiert kein Browser. */
  | "unsicher"
  /** Sonst: über das Menü des Browsers. */
  | "browser";

type Angebot = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let angebot: Angebot | null = null;
let installiert = false;
const hoerer = new Set<() => void>();

function melde() {
  hoerer.forEach((h) => h());
}

let gefangen = false;

export function fangeInstallAngebot() {
  if (gefangen || typeof window === "undefined") return;
  gefangen = true;
  window.addEventListener("beforeinstallprompt", (e) => {
    // Kein eigenes Mini-Banner des Browsers — der Knopf steht in den
    // Einstellungen.
    e.preventDefault();
    angebot = e as Angebot;
    melde();
  });
  window.addEventListener("appinstalled", () => {
    angebot = null;
    installiert = true;
    melde();
  });
}

export function beobachteInstallLage(h: () => void): () => void {
  hoerer.add(h);
  return () => hoerer.delete(h);
}

export function laeuftAlsApp(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // Safari auf iPhone/iPad
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export function istIos(ua: string, maxTouchPoints: number): boolean {
  // iPadOS meldet sich als Mac — erkennbar an der Berührung.
  return /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && maxTouchPoints > 1);
}

export function installLage(): InstallLage {
  if (installiert || laeuftAlsApp()) return "installiert";
  if (!window.isSecureContext) return "unsicher";
  if (angebot) return "angebot";
  if (istIos(navigator.userAgent, navigator.maxTouchPoints)) return "ios";
  return "browser";
}

/** Zeigt den Dialog des Browsers. Ein Angebot gilt nur einmal. */
export async function installiere(): Promise<boolean> {
  const a = angebot;
  if (!a) return false;
  angebot = null;
  await a.prompt();
  const { outcome } = await a.userChoice;
  if (outcome === "accepted") installiert = true;
  melde();
  return outcome === "accepted";
}
