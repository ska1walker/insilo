import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

export const SUPPORTED_LOCALES = ["de", "en", "fr", "es", "it"] as const;
export const DEFAULT_LOCALE = "de" as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];
export const LOCALE_COOKIE = "insilo-locale";

function pickFromAcceptLanguage(header: string | null): Locale | null {
  if (!header) return null;
  // "en-US,en;q=0.9,fr;q=0.5" → ["en-US", "en", "fr"]
  const tags = header
    .split(",")
    .map((part) => {
      const [tag] = part.trim().split(";");
      return tag.trim().toLowerCase();
    })
    .filter(Boolean);
  for (const tag of tags) {
    const primary = tag.split("-")[0] as Locale;
    if ((SUPPORTED_LOCALES as readonly string[]).includes(primary)) {
      return primary;
    }
  }
  return null;
}

/**
 * Single-route i18n config — keine /[locale]/-Segments in der URL.
 * Resolution priorisiert:
 *   1. Cookie `insilo-locale` (gesetzt vom Locale-Switcher in /einstellungen)
 *   2. Browser `Accept-Language`-Header
 *   3. Hardcoded Default `de`
 *
 * Die persistente Org-/User-Setting aus der DB wird beim Frontend-Load
 * über `GET /api/v1/locale` gezogen und in das Cookie geschrieben —
 * damit greift Stage 1 ab der zweiten Page-Navigation.
 */
export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get(LOCALE_COOKIE)?.value as Locale | undefined;

  let locale: Locale;
  if (cookieLocale && (SUPPORTED_LOCALES as readonly string[]).includes(cookieLocale)) {
    locale = cookieLocale;
  } else {
    const headerStore = await headers();
    locale =
      pickFromAcceptLanguage(headerStore.get("accept-language")) ?? DEFAULT_LOCALE;
  }

  const messages = (await import(`../messages/${locale}.json`)).default;

  return {
    locale,
    messages,
  };
});
