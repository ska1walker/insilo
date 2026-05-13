"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchSettings,
  updateSettings,
  type SettingsRead,
} from "@/lib/api/settings";

type Phase = "loading" | "ready" | "saving" | "error";

type FormState = {
  baseUrl: string;
  model: string;
  apiKey: string;
  /** True once the user has typed into the key field — only then do we send it. */
  keyEdited: boolean;
  clearKey: boolean;
};

const initialForm: FormState = {
  baseUrl: "",
  model: "",
  apiKey: "",
  keyEdited: false,
  clearKey: false,
};

export default function EinstellungenPage() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [settings, setSettings] = useState<SettingsRead | null>(null);
  const [form, setForm] = useState<FormState>(initialForm);
  const [savedAt, setSavedAt] = useState<number | null>(null);

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
        });
        setPhase("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        console.error("settings load failed", err);
        setError("Einstellungen konnten nicht geladen werden.");
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
      const updated = await updateSettings({
        llm_base_url: form.baseUrl,
        llm_api_key,
        llm_model: form.model,
      });
      setSettings(updated);
      setForm({
        baseUrl: updated.llm_base_url,
        model: updated.llm_model,
        apiKey: "",
        keyEdited: false,
        clearKey: false,
      });
      setSavedAt(Date.now());
      setPhase("ready");
    } catch (err: unknown) {
      console.error("settings save failed", err);
      setError("Speichern fehlgeschlagen. Bitte erneut versuchen.");
      setPhase("ready");
    }
  }

  if (phase === "loading") {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12">
        <p className="text-sm text-text-secondary">Wird geladen…</p>
      </main>
    );
  }

  if (phase === "error" && !settings) {
    return (
      <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12">
        <p className="text-sm text-error">{error}</p>
      </main>
    );
  }

  const s = settings!;
  const hint = s.llm_api_key_set ? s.llm_api_key_hint : "—";
  const effectiveBaseUrl = form.baseUrl.trim() || s.defaults.llm_base_url;
  const effectiveModel = form.model.trim() || s.defaults.llm_model;

  return (
    <main className="mx-auto max-w-[720px] px-6 py-12 md:px-12">
      <Link href="/" className="text-sm text-text-secondary hover:text-text-primary">
        ← Übersicht
      </Link>

      <div className="mt-6 mb-10">
        <h1 className="font-display text-4xl font-medium tracking-tight">
          Einstellungen
        </h1>
        <p className="mt-3 max-w-prose text-text-secondary">
          Verbinden Sie Insilo mit Ihrem bevorzugten Sprachmodell. Jeder
          OpenAI-kompatible Endpunkt funktioniert — die lokale Olares-LiteLLM,
          ein eigener Ollama-Server oder ein externer Anbieter. Wenn ein Feld
          leer bleibt, nutzt Insilo die im Deployment hinterlegten Vorgaben.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-7 rounded-lg border border-border-subtle bg-white p-7"
      >
        <header>
          <h2 className="font-display text-xl font-medium">Sprachmodell</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Wird für Zusammenfassungen und die „Fragen"-Funktion verwendet.
          </p>
        </header>

        <Field
          label="Endpunkt-URL"
          hint="z. B. https://api.openai.com/v1 oder http://litellm-svc.litellm-…/v1"
          placeholder={s.defaults.llm_base_url}
        >
          <input
            type="url"
            className="input w-full"
            value={form.baseUrl}
            placeholder={s.defaults.llm_base_url}
            onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
            autoComplete="off"
            spellCheck={false}
          />
        </Field>

        <Field
          label="API-Schlüssel"
          hint={
            s.llm_api_key_set
              ? `Hinterlegt: ${hint}. Leer lassen, um den Schlüssel beizubehalten.`
              : "Bei Anbietern wie OpenAI mit sk- beginnend. Wird verschlüsselt übertragen, niemals zurückgegeben."
          }
        >
          <div className="flex gap-2">
            <input
              type="password"
              className="input flex-1"
              value={form.apiKey}
              placeholder={s.llm_api_key_set ? "•••••••••• (beibehalten)" : "sk-…"}
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
                className="btn-tertiary"
                onClick={() =>
                  setForm({
                    ...form,
                    clearKey: !form.clearKey,
                    apiKey: "",
                    keyEdited: false,
                  })
                }
              >
                {form.clearKey ? "Doch behalten" : "Schlüssel löschen"}
              </button>
            )}
          </div>
        </Field>

        <Field
          label="Modell-ID"
          hint="Modellname wie er beim Endpunkt registriert ist, z. B. gpt-4o, qwen36a3bvisionone, llama3.1:8b."
          placeholder={s.defaults.llm_model}
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

        <div className="rounded-md bg-surface-soft px-4 py-3 text-xs text-text-secondary">
          <p className="font-medium text-text-primary">Aktiv beim Speichern</p>
          <p className="mt-1">
            Endpunkt: <span className="font-mono">{effectiveBaseUrl || "—"}</span>
          </p>
          <p>
            Modell: <span className="font-mono">{effectiveModel || "—"}</span>
          </p>
        </div>

        {error && <p className="text-sm text-error">{error}</p>}

        <div className="flex items-center justify-between border-t border-border-subtle pt-5">
          <p className="text-xs text-text-secondary">
            {savedAt && phase === "ready" ? "Gespeichert." : " "}
          </p>
          <button
            type="submit"
            className="btn-primary"
            disabled={phase === "saving"}
          >
            {phase === "saving" ? "Wird gespeichert…" : "Speichern"}
          </button>
        </div>
      </form>

      <p className="mt-6 text-xs text-text-secondary">
        Hinweis: Bestehende Zusammenfassungen werden nicht neu generiert. Die
        neuen Einstellungen gelten für künftige Aufnahmen und Fragen.
      </p>
    </main>
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
      <span className="block text-sm font-medium text-text-primary">{label}</span>
      {hint && (
        <span className="mt-1 mb-2 block text-xs text-text-secondary">{hint}</span>
      )}
      {children}
    </label>
  );
}
