import type { Metadata, Viewport } from "next";
import { Lexend_Deca, Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import { ServiceWorkerRegister } from "@/components/service-worker-register";
import { ToastProvider } from "@/components/toast";
import "./globals.css";

const lexend = Lexend_Deca({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-display",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
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
      className={`${lexend.variable} ${inter.variable} ${jetbrains.variable}`}
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
                  <Link href="/idee" className="btn-tertiary hidden md:inline-flex">
                    {t("idee")}
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
