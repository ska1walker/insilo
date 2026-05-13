import type { Metadata, Viewport } from "next";
import { Lexend_Deca, Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { ServiceWorkerRegister } from "@/components/service-worker-register";
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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="de"
      className={`${lexend.variable} ${inter.variable} ${jetbrains.variable}`}
    >
      <body>
        <header className="sticky top-0 z-40 border-b border-border-subtle bg-white/90 backdrop-blur">
          <div className="mx-auto flex max-w-[1280px] items-center justify-between px-6 py-4 md:px-12">
            <Link
              href="/"
              className="font-display text-lg font-medium tracking-tight"
            >
              insilo
            </Link>
            <nav className="flex items-center gap-2">
              <Link href="/ask" className="btn-tertiary">
                Fragen
              </Link>
              <Link href="/einstellungen" className="btn-tertiary">
                Einstellungen
              </Link>
              <Link href="/style" className="btn-tertiary hidden md:inline-flex">
                Design
              </Link>
              <Link href="/aufnahme" className="btn-primary">
                Aufnahme
              </Link>
            </nav>
          </div>
        </header>
        {children}
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}
