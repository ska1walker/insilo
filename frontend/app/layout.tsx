import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { ShowerHead } from "lucide-react";
import Link from "next/link";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
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
};

export const viewport: Viewport = {
  themeColor: "#0A0A0A",
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
  const t = await getTranslations("nav");

  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <ToastProvider>
            <header className="sticky top-0 z-40 border-b border-border-subtle bg-white/90 backdrop-blur">
              <div className="mx-auto flex max-w-[1280px] items-center justify-between px-6 py-4 md:px-12">
                <Link href="/" aria-label={t("homeAria")} className="inline-flex items-center">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="/insilo_logo.svg"
                    alt={t("logoAlt")}
                    height={28}
                    className="h-7 w-auto"
                  />
                </Link>
                <nav className="flex items-center gap-2">
                  <Link href="/besprechungen" className="btn-tertiary">
                    {t("meetings")}
                  </Link>
                  <Link href="/archiv" className="btn-tertiary">
                    {t("archive")}
                  </Link>
                  <Link href="/einstellungen" className="btn-tertiary">
                    {t("settings")}
                  </Link>
                  <Link href="/ueber" className="btn-tertiary hidden md:inline-flex">
                    {t("about")}
                  </Link>
                  <Link
                    href="/idee"
                    aria-label={t("idee")}
                    title={t("idee")}
                    className="quick-capture-trigger"
                  >
                    <ShowerHead className="h-5 w-5" strokeWidth={1.75} aria-hidden />
                  </Link>
                  <Link href="/aufnahme" className="btn-primary">
                    {t("record")}
                  </Link>
                </nav>
              </div>
            </header>
            {children}
            <ServiceWorkerRegister />
          </ToastProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
