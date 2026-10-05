"use client";

/**
 * „Als App" in den Einstellungen: Insilo auf den Startbildschirm legen.
 *
 * Was hier steht, hängt vom Browser ab (lib/installation.ts): ein Knopf,
 * wo der Browser selbst installieren kann, sonst der Weg in Worten. Vor
 * der Hydration steht nur der Hinweis — der Server kennt das Gerät nicht.
 */

import { Check, Download, Smartphone } from "@/lib/symbole";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import {
  beobachteInstallLage,
  installLage,
  installiere,
  type InstallLage,
} from "@/lib/installation";

export function AppInstallieren() {
  const t = useTranslations("installation");
  const [lage, setLage] = useState<InstallLage | null>(null);

  useEffect(() => {
    const auffrischen = () => setLage(installLage());
    auffrischen();
    return beobachteInstallLage(auffrischen);
  }, []);

  return (
    <div className="space-y-4 rounded-lg border border-trennlinie bg-seite p-6">
      <header>
        <h3 className="text-sm font-medium text-text-primaer">{t("title")}</h3>
        <p className="mt-1 text-xs text-text-sekundaer">{t("hint")}</p>
      </header>

      {lage === "installiert" ? (
        <p className="flex items-center gap-3 text-sm text-text-primaer">
          <Check size={16} style={{ color: "var(--am-gold-beschriftung)" }} aria-hidden />
          {t("installiert")}
        </p>
      ) : lage === "angebot" ? (
        <button
          type="button"
          className="btn btn-primaer"
          onClick={() => void installiere()}
        >
          <Download size={16} aria-hidden />
          {t("installieren")}
        </button>
      ) : lage !== null ? (
        <p className="flex items-start gap-3 text-sm text-text-sekundaer">
          <Smartphone size={16} className="mt-0.5 shrink-0" aria-hidden />
          {t(lage)}
        </p>
      ) : null}
    </div>
  );
}
