import { apiGet, apiPut } from "./client";

export const SUPPORTED_LOCALES = ["de", "en", "fr", "es", "it"] as const;
export type LocaleCode = (typeof SUPPORTED_LOCALES)[number];
export type LocaleSource = "user" | "org" | "browser" | "default";

export type LocaleRead = {
  active: LocaleCode;
  source: LocaleSource;
  available: LocaleCode[];
  user_setting: LocaleCode | null;
  org_setting: LocaleCode | null;
};

export function fetchLocale(): Promise<LocaleRead> {
  return apiGet<LocaleRead>("/api/v1/locale");
}

export function setLocale(
  locale: LocaleCode | null,
  scope: "user" | "org" = "user",
): Promise<void> {
  return apiPut("/api/v1/locale", { locale, scope });
}
