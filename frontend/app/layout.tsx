import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { DARSTELLUNG_SCRIPT } from "@/components/darstellung";
import { Huelle } from "@/components/huelle";
import { ServiceWorkerRegister } from "@/components/service-worker-register";
import { ToastProvider } from "@/components/toast";
import "./globals.css";

// Geist als Variable Fonts aus dem Repo — kein Google-CDN, auch nicht zur
// Bauzeit. Das AImighty-Designsystem schreibt Selbst-Hosting vor, und die
// Datensouveränitäts-Zusage duldet ohnehin keinen Fremdabruf.
const geistSans = localFont({
  src: "./fonts/Geist-Variable.woff2",
  weight: "100 900",
  variable: "--font-geist-sans",
  display: "swap",
});

const geistMono = localFont({
  src: "./fonts/GeistMono-Variable.woff2",
  weight: "100 900",
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  // Im Tab steht zuerst die Seite, dann die Anwendung („Aufnahme · Insilo“,
  // CI ABGLEICH G7). Seiten setzen nur ihren eigenen Namen als `title`;
  // ohne eigenen Titel steht nur „Insilo“.
  title: { default: "Insilo", template: "%s · Insilo" },
  description:
    "On-Premise Aufnahme, Transkription und Analyse von Geschäftsgesprächen — vollständig auf der Hardware des Kunden.",
  manifest: "/manifest.json",
  // Symbole bewusst nicht über die Metadaten (`icons` hier oder
  // app/icon.*): Next 15.5 rendert dann eine Marke <meta name="«nxt-icon»">,
  // die es beim Streamen nur entfernt, wenn sie in einem Stück des
  // Datenstroms liegt — sonst bleibt sie stehen und der Browser meldet
  // React #418 (so in Rocket gefunden). Die Link-Tags stehen deshalb unten
  // im <head>. Unter dem Symbol auf dem Home-Bildschirm steht „Insilo“.
  appleWebApp: { title: "Insilo" },
};

export const viewport: Viewport = {
  themeColor: "#051729",
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        {/* Setzt die Klasse `dunkel` vor dem ersten Anstrich. Ohne das
            blitzt bei dunkler Einstellung kurz die helle Fläche auf. */}
        <script dangerouslySetInnerHTML={{ __html: DARSTELLUNG_SCRIPT }} />
        {/* Im Tab nur das Mikrofon (SVG folgt der Tableiste, PNG für
            Safari), auf dem Home-Bildschirm die volle Kachel — alles aus
            scripts/icons.mjs (CI R5/G7). iOS liest die Manifest-Symbole
            nicht und braucht apple-touch-icon ausdrücklich. */}
        <link rel="icon" href="/icons/tab.svg" type="image/svg+xml" sizes="any" />
        <link rel="icon" href="/icons/tab-32.png" type="image/png" sizes="32x32" />
        <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" type="image/png" sizes="180x180" />
      </head>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <ToastProvider>
            <Huelle>{children}</Huelle>
            <ServiceWorkerRegister />
          </ToastProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
