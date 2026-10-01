"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiKeyManager } from "@/components/api-key-manager";
import { DarstellungSwitcher } from "@/components/darstellung";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { SpeakerCatalog } from "@/components/speaker-catalog";
import { TagManager } from "@/components/tag-manager";
import { TemplatePrompts } from "@/components/template-prompts";
import { WebhookManager } from "@/components/webhook-manager";
import {
  fetchSettings,
  testSettings,
  updateSettings,
  type SettingsRead,
  type TestResult,
} from "@/lib/api/settings";

type Phase = "loading" | "ready" | "saving" | "error";

type FormState = {
  baseUrl: string;
  model: string;
  apiKey: string;
  /** True once the user has typed into the key field — only then do we send it. */
  keyEdited: boolean;
  clearKey: boolean;

  /** Spracherkennung. Leer = mitgelieferter Dienst auf dieser Box. */
  sttBaseUrl: string;
  sttModel: string;
  sttApiKey: string;
  sttKeyEdited: boolean;
  sttClearKey: boolean;
};

const initialForm: FormState = {
  baseUrl: "",
  model: "",
  apiKey: "",
  keyEdited: false,
  clearKey: false,
  sttBaseUrl: "",
  sttModel: "",
  sttApiKey: "",
  sttKeyEdited: false,
  sttClearKey: false,
};

export default function EinstellungenPage() {
  const t = useTranslations("einstellungen");
  const tSettings = useTranslations("settings");
  const tTags = useTranslations("tags");
  const tCommon = useTranslations("common");
  const tErrors = useTranslations("errors");
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<SettingsRead | null>(null);
  const [form, setForm] = useState<FormState>(initialForm);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then((s) => {
        if (cancelled) return;
        setSettings(s);
        setForm({
          baseUrl: s.llm_base_url,
          model: s.llm_model,
          apiKey: "",
          keyEdited: false,
          clearKey: false,
          sttBaseUrl: s.stt_base_url,
          sttModel: s.stt_model,
          sttApiKey: "",
          sttKeyEdited: false,
          sttClearKey: false,
        });
        setPhase("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        console.error("settings load failed", err);
        setError(t("loadFailed"));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await testSettings({
        baseUrl: form.baseUrl,
        apiKey: form.apiKey,
        model: form.model,
      });
      setTestResult(r);
    } catch (err: unknown) {
      console.error("settings test failed", err);
      setTestResult({
        ok: false,
        detail: t("testUnreachable"),
      });
    } finally {
      setTesting(false);
    }
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setPhase("saving");
    setError(null);

    let llm_api_key: string | null;
    if (form.clearKey) {
      llm_api_key = "";
    } else if (form.keyEdited) {
      llm_api_key = form.apiKey;
    } else {
      llm_api_key = null;
    }

    try {
      // Gleiche Regel wie beim Sprachmodell: nur ein wirklich angefasstes
      // Feld wird geschickt, sonst bleibt der hinterlegte Schlüssel stehen.
      let stt_api_key: string | null;
      if (form.sttClearKey) {
        stt_api_key = "";
      } else if (form.sttKeyEdited) {
        stt_api_key = form.sttApiKey;
      } else {
        stt_api_key = null;
      }

      const updated = await updateSettings({
        llm_base_url: form.baseUrl,
        llm_api_key,
        llm_model: form.model,
        stt_base_url: form.sttBaseUrl,
        stt_api_key,
        stt_model: form.sttModel,
      });
      setSettings(updated);
      setForm({
        baseUrl: updated.llm_base_url,
        model: updated.llm_model,
        apiKey: "",
        keyEdited: false,
        clearKey: false,
        sttBaseUrl: updated.stt_base_url,
        sttModel: updated.stt_model,
        sttApiKey: "",
        sttKeyEdited: false,
        sttClearKey: false,
      });
      setSavedAt(Date.now());
      setPhase("ready");
    } catch (err: unknown) {
      console.error("settings save failed", err);
      setError(tErrors("saveFailed"));
      setPhase("ready");
    }
  }

  if (phase === "loading") {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12">
        <p className="text-sm text-text-sekundaer">{tCommon("loading")}</p>
      </main>
    );
  }

  if (phase === "error" && !settings) {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12">
        <p className="text-sm text-fehler">{error}</p>
      </main>
    );
  }

  const s = settings!;
  const hint = s.llm_api_key_set ? s.llm_api_key_hint : "—";
  const sttHint = s.stt_api_key_set ? s.stt_api_key_hint : "—";
  const effectiveBaseUrl = form.baseUrl.trim() || s.defaults.llm_base_url;
  const effectiveModel = form.model.trim() || s.defaults.llm_model;

  return (
    <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12">
      <Link href="/" className="text-sm text-text-sekundaer hover:text-text-primaer">
        ← {tCommon("overview")}
      </Link>

      <div className="mt-6 mb-10">
        <h1 className="font-display text-4xl font-medium tracking-tight">
          {t("title")}
        </h1>
        <p className="mt-3 max-w-prose text-text-sekundaer">
          {t("intro")}
        </p>
      </div>

      <section className="mb-10 space-y-4">
        <LocaleSwitcher />
        <DarstellungSwitcher />
      </section>

      {/* Ohne eingetragene Adresse laufen Aufnahme und Transkription,
          aber keine Zusammenfassung. Das gehört gesagt, bevor jemand eine
          Besprechung aufnimmt und sich über das fehlende Protokoll
          wundert. Kein Fehlerton — es fehlt etwas, kaputt ist nichts. */}
      {settings !== null && !settings.llm_base_url && !settings.defaults?.llm_base_url && (
        <div className="streifen streifen-hinweis mb-6">
          <span className="zeichen" aria-hidden>
            i
          </span>
          <span>
            <strong className="block">{tSettings("llmFehltTitel")}</strong>
            {tSettings("llmFehltText")}
            <span className="mt-2 block text-[0.8125rem] text-text-gedaempft">
              {tSettings("llmFehltWoher")}
            </span>
          </span>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="space-y-7 rounded-lg border border-trennlinie bg-seite p-7"
      >
        <header>
          <h2 className="font-display text-xl font-medium">{t("sectionLlm")}</h2>
          <p className="mt-1 text-sm text-text-sekundaer">
            {t("llmHint")}
          </p>
        </header>

        <Field
          label={t("llmUrl")}
          hint={t("llmUrlHint")}
        >
          <input
            type="url"
            className="input w-full"
            value={form.baseUrl}
            placeholder={s.defaults.llm_base_url || t("llmUrlPlaceholder")}
            onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
            autoComplete="off"
            spellCheck={false}
          />
        </Field>

        <Field
          label={tSettings("sttKey")}
          hint={
            s.llm_api_key_set
              ? t("keyStored", { hint })
              : t("llmKeyHint")
          }
        >
          <div className="flex gap-2">
            <input
              type="password"
              className="input flex-1"
              value={form.apiKey}
              placeholder={s.llm_api_key_set ? t("keyKeepPlaceholder") : "sk-…"}
              onChange={(e) =>
                setForm({
                  ...form,
                  apiKey: e.target.value,
                  keyEdited: true,
                  clearKey: false,
                })
              }
              autoComplete="off"
              spellCheck={false}
              disabled={form.clearKey}
            />
            {s.llm_api_key_set && (
              <button
                type="button"
                className="btn btn-still"
                onClick={() =>
                  setForm({
                    ...form,
                    clearKey: !form.clearKey,
                    apiKey: "",
                    keyEdited: false,
                  })
                }
              >
                {form.clearKey ? t("keyKeep") : t("keyDelete")}
              </button>
            )}
          </div>
        </Field>

        <Field
          label={tSettings("sttModell")}
          hint={tSettings("sttModellHinweis")}
        >
          <input
            type="text"
            className="input w-full"
            value={form.model}
            placeholder={s.defaults.llm_model}
            onChange={(e) => setForm({ ...form, model: e.target.value })}
            autoComplete="off"
            spellCheck={false}
          />
        </Field>

        <div className="rounded-md bg-flaeche-1 px-4 py-3 text-xs text-text-sekundaer">
          <p className="font-medium text-text-primaer">{t("effectiveTitle")}</p>
          <p className="mt-1">
            {t("effectiveEndpoint")}:{" "}
            <span className="font-mono">{effectiveBaseUrl || "—"}</span>
          </p>
          <p>
            {t("effectiveModel")}:{" "}
            <span className="font-mono">{effectiveModel || "—"}</span>
          </p>
        </div>

        {testResult && (
          <div
            className="rounded-md border px-4 py-3 text-sm"
            style={
              testResult.ok
                ? {
                    borderColor: "var(--am-erfolg)",
                    color: "var(--am-erfolg)",
                    background: "var(--am-erfolg-flaeche)",
                  }
                : {
                    borderColor: "var(--am-fehler)",
                    color: "var(--am-fehler)",
                    background: "var(--am-fehler-flaeche)",
                  }
            }
          >
            <p className="font-medium">
              {testResult.ok ? t("testOk") : t("testFailed")}
            </p>
            <p className="mt-1 text-xs opacity-90">
              {testResult.detail}
              {testResult.ok && testResult.elapsed_ms != null && (
                <>
                  {" · "}{testResult.elapsed_ms} ms
                  {testResult.model && <> · {testResult.model}</>}
                </>
              )}
            </p>
          </div>
        )}

        {/* ── Spracherkennung ────────────────────────────────────────
            Bewusst im selben Formular und ohne eigenen Speichern-Knopf:
            das Designsystem erlaubt genau eine primäre Handlung je
            Ansicht. Ein zweiter Knopf sähe nach zwei getrennten
            Einstellungen aus, die man einzeln vergessen kann. */}
        <div className="space-y-5 border-t border-trennlinie pt-7">
          <header>
            <h2 className="font-display text-xl font-medium">
              {tSettings("sttTitel")}
            </h2>
            <p className="mt-1 text-sm text-text-sekundaer">
              {tSettings("sttHinweis")}
            </p>
          </header>

          <Field label={tSettings("sttUrl")} hint={tSettings("sttUrlHinweis")}>
            <input
              type="url"
              className="input w-full"
              value={form.sttBaseUrl}
              onChange={(e) => setForm({ ...form, sttBaseUrl: e.target.value })}
              autoComplete="off"
              spellCheck={false}
            />
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field
              label={tSettings("sttKey")}
              hint={
                s.stt_api_key_set
                  ? t("keyStored", { hint: sttHint })
                  : tSettings("sttKeyHinweis")
              }
            >
              <div className="flex gap-2">
                <input
                  type="password"
                  className="input w-full"
                  value={form.sttApiKey}
                  placeholder={
                    form.sttClearKey
                      ? t("keyWillBeDeleted")
                      : s.stt_api_key_set
                        ? t("keyKeepPlaceholder")
                        : ""
                  }
                  disabled={form.sttClearKey}
                  onChange={(e) =>
                    setForm({ ...form, sttApiKey: e.target.value, sttKeyEdited: true })
                  }
                  autoComplete="off"
                />
                {s.stt_api_key_set && (
                  <button
                    type="button"
                    className="btn btn-still shrink-0"
                    onClick={() =>
                      setForm({
                        ...form,
                        sttClearKey: !form.sttClearKey,
                        sttApiKey: "",
                        sttKeyEdited: false,
                      })
                    }
                  >
                    {form.sttClearKey ? t("keyKeep") : tCommon("delete")}
                  </button>
                )}
              </div>
            </Field>

            <Field label={tSettings("sttModell")} hint={tSettings("sttModellHinweis")}>
              <input
                type="text"
                className="input w-full"
                value={form.sttModel}
                onChange={(e) => setForm({ ...form, sttModel: e.target.value })}
                autoComplete="off"
                spellCheck={false}
              />
            </Field>
          </div>

          {/* Adresse ohne Modell-ID: der Endpunkt lehnt dann jede Anfrage
              ab (HTTP 422). Das ist keine Datenschutzfrage, sondern eine
              unfertige Einrichtung — und sie hat Vorrang, weil sie die
              Transkription stillstehen lässt. */}
          {form.sttBaseUrl.trim() !== "" && form.sttModel.trim() === "" && (
            <div className="streifen streifen-hinweis">
              <span className="zeichen" aria-hidden>
                i
              </span>
              <span>{tSettings("sttModellFehlt")}</span>
            </div>
          )}

          {/* Farbe trägt die Aussage nicht allein — Zeichen und Satz dazu.
              Der Streifen erscheint nur, wenn wirklich eine Adresse steht:
              ohne Eintrag gibt es nichts zu warnen. */}
          {form.sttBaseUrl.trim() !== "" && (
            <div className="streifen streifen-achtung">
              <span className="zeichen" aria-hidden>
                !
              </span>
              <span>{tSettings("sttWarnung")}</span>
            </div>
          )}
        </div>

        {error && <p className="text-sm text-fehler">{error}</p>}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-trennlinie pt-5">
          <p className="text-xs text-text-sekundaer">
            {savedAt && phase === "ready" ? t("saved") : " "}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleTest}
              className="btn btn-sekundaer"
              disabled={testing || phase === "saving"}
            >
              {testing ? t("testing") : t("test")}
            </button>
            <button
              type="submit"
              className="btn btn-primaer"
              disabled={phase === "saving"}
            >
              {phase === "saving" ? tCommon("saving") : tCommon("save")}
            </button>
          </div>
        </div>
      </form>

      <p className="mt-6 text-xs text-text-sekundaer">
        {t("afterSave")}
      </p>

      <section className="mt-14">
        <header className="mb-5">
          <h2 className="font-display text-xl font-medium">
            {t("sectionTemplates")}
          </h2>
          <p className="mt-2 max-w-prose text-sm text-text-sekundaer">
            {t("sectionTemplatesHint")}
          </p>
        </header>

        <TemplatePrompts />
      </section>

      <section className="mt-14">
        <header className="mb-5">
          <h2 className="font-display text-xl font-medium">{t("sectionSpeakers")}</h2>
          <p className="mt-2 max-w-prose text-sm text-text-sekundaer">
            {t("sectionSpeakersHint")}
          </p>
        </header>

        <SpeakerCatalog />
      </section>

      <section className="mt-14">
        <header className="mb-5">
          <h2 className="font-display text-xl font-medium">{tTags("sectionTitle")}</h2>
          <p className="mt-2 max-w-prose text-sm text-text-sekundaer">
            {tTags("sectionHint")}
          </p>
        </header>

        <TagManager />
      </section>

      <section className="mt-14">
        <header className="mb-5">
          <h2 className="font-display text-xl font-medium">{t("sectionWebhooks")}</h2>
          <p className="mt-2 max-w-prose text-sm text-text-sekundaer">
            {t.rich("sectionWebhooksHint", { code: codeTag })}
          </p>
        </header>

        <WebhookManager />
      </section>

      <section className="mt-14 pb-12">
        <header className="mb-5">
          <h2 className="font-display text-xl font-medium">{t("sectionApiKeys")}</h2>
          <p className="mt-2 max-w-prose text-sm text-text-sekundaer">
            {t.rich("sectionApiKeysHint", { code: codeTag })}
          </p>
        </header>

        <ApiKeyManager />
      </section>
    </main>
  );
}

function codeTag(teile: React.ReactNode) {
  return (
    <code className="rounded bg-flaeche-1 px-1 font-mono">{teile}</code>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  placeholder?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-text-primaer">{label}</span>
      {hint && (
        <span className="mt-1 mb-2 block text-xs text-text-sekundaer">{hint}</span>
      )}
      {children}
    </label>
  );
}
