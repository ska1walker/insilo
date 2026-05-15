"use client";

import { Check, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
// next-intl Cookie-Key — referenziert in i18n/request.ts
import {
  fetchLocale,
  setLocale as putLocale,
  SUPPORTED_LOCALES,
  type LocaleCode,
  type LocaleRead,
} from "@/lib/api/locale";

const LOCALE_COOKIE = "insilo-locale";

function setCookie(name: string, value: string | null, days = 365) {
  if (typeof document === "undefined") return;
  const expires = new Date();
  if (value === null) {
    document.cookie = `${name}=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT`;
    return;
  }
  expires.setTime(expires.getTime() + days * 86400 * 1000);
  document.cookie = `${name}=${value}; Path=/; Expires=${expires.toUTCString()}; SameSite=Lax`;
}

/**
 * UI-Spracheinstellung in /einstellungen. Speichert
 * - Cookie `insilo-locale` (sofortiger Effekt nach Reload)
 * - Backend `users.ui_locale` oder `org_settings.ui_locale` (Persistenz)
 */
export function LocaleSwitcher() {
  const t = useTranslations("locale");
  const tNames = useTranslations("locale.names");
  const toast = useToast();
  const [state, setState] = useState<LocaleRead | null>(null);
  const [saving, setSaving] = useState<LocaleCode | "auto" | null>(null);
  const [orgScope, setOrgScope] = useState(false);

  useEffect(() => {
    fetchLocale().then(setState).catch(() => setState(null));
  }, []);

  async function pick(locale: LocaleCode | null) {
    setSaving(locale ?? "auto");
    try {
      await putLocale(locale, orgScope ? "org" : "user");
      setCookie(LOCALE_COOKIE, locale);
      toast.show({ message: t("saved"), variant: "success" });
      // Reload, damit next-intl die neue Locale + Messages lädt.
      window.location.reload();
    } catch (err) {
      console.error("save locale failed", err);
      toast.show({ message: t("saveFailed"), variant: "error" });
      setSaving(null);
    }
  }

  if (state === null) {
    return <div className="h-24 animate-pulse rounded bg-surface-soft" />;
  }

  const activeIsUser = state.user_setting !== null;
  const activeIsOrg = state.user_setting === null && state.org_setting !== null;

  return (
    <div className="space-y-4 rounded-lg border border-border-subtle bg-white p-6">
      <header>
        <h3 className="text-sm font-medium text-text-primary">{t("switcherTitle")}</h3>
        <p className="mt-1 text-xs text-text-secondary">{t("switcherHint")}</p>
      </header>

      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        <LocaleOption
          label={t("optionAuto")}
          hint={t("optionAutoHint")}
          selected={!activeIsUser && !activeIsOrg}
          loading={saving === "auto"}
          onClick={() => pick(null)}
        />
        {SUPPORTED_LOCALES.map((code) => (
          <LocaleOption
            key={code}
            label={tNames(code)}
            hint={
              state.active === code
                ? state.source === "user"
                  ? "Ihre Wahl"
                  : state.source === "org"
                  ? "Org-Standard"
                  : state.source === "browser"
                  ? "Browser-Erkennung"
                  : "Standard"
                : undefined
            }
            selected={state.user_setting === code}
            loading={saving === code}
            onClick={() => pick(code)}
          />
        ))}
      </div>

      <label className="inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={orgScope}
          onChange={(e) => setOrgScope(e.target.checked)}
          disabled={saving !== null}
        />
        <span>{t("saveScopeOrg")}</span>
      </label>
    </div>
  );
}

function LocaleOption({
  label,
  hint,
  selected,
  loading,
  onClick,
}: {
  label: string;
  hint?: string;
  selected: boolean;
  loading: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={`flex items-start gap-3 rounded-md border px-4 py-3 text-left transition ${
        selected
          ? "border-gold-deep bg-gold-faint"
          : "border-border-subtle bg-white hover:bg-surface-soft"
      }`}
      style={
        selected
          ? { borderColor: "var(--gold-deep)", background: "var(--gold-faint)" }
          : undefined
      }
    >
      <span className="mt-0.5 inline-flex h-4 w-4 items-center justify-center">
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-text-meta" strokeWidth={1.75} />
        ) : selected ? (
          <Check className="h-3.5 w-3.5" strokeWidth={2} style={{ color: "var(--gold-deep)" }} />
        ) : (
          <span className="h-3 w-3 rounded-full border border-border-strong" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-text-primary">{label}</span>
        {hint && <span className="mt-0.5 block text-xs text-text-meta">{hint}</span>}
      </span>
    </button>
  );
}
