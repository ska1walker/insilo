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
  title: "insilo — Datensouveräne Meeting-Intelligenz",
  description:
    "On-Premise Aufnahme, Transkription und Analyse von Geschäftsgesprächen — vollständig auf der Hardware des Kunden.",
  manifest: "/manifest.json",
  // iOS liest die Icons aus dem Manifest nicht — es braucht
  // apple-touch-icon ausdrücklich.
  icons: {
    icon: "/icons/icon-192.png",
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#051729",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
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
