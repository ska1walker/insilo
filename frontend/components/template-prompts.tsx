"use client";

import { useEffect, useState } from "react";
import {
  getTemplate,
  listTemplates,
  resetTemplatePrompt,
  updateTemplatePrompt,
  type TemplateDetail,
  type TemplateDto,
} from "@/lib/api/templates";

type EditorState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "saving" }
  | { kind: "resetting" };

export function TemplatePrompts() {
  const [list, setList] = useState<TemplateDto[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listTemplates()
      .then((tpls) => {
        if (!cancelled) setList(tpls);
      })
      .catch(() => {
        if (!cancelled) setList([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function refreshList() {
    listTemplates().then((tpls) => setList(tpls)).catch(() => {});
  }

  if (list === null) {
    return (
      <div className="space-y-2">
        <div className="h-14 animate-pulse rounded bg-surface-soft" />
        <div className="h-14 animate-pulse rounded bg-surface-soft" />
      </div>
    );
  }

  if (list.length === 0) {
    return (
      <p className="text-sm text-text-secondary">
        Keine Vorlagen gefunden.
      </p>
    );
  }

  return (
    <div className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-white">
      {list.map((t) => (
        <TemplateRow
          key={t.id}
          template={t}
          open={openId === t.id}
          onToggle={() => setOpenId(openId === t.id ? null : t.id)}
          onSaved={() => {
            refreshList();
          }}
          onReset={() => {
            refreshList();
          }}
        />
      ))}
    </div>
  );
}

function TemplateRow({
  template,
  open,
  onToggle,
  onSaved,
  onReset,
}: {
  template: TemplateDto;
  open: boolean;
  onToggle: () => void;
  onSaved: () => void;
  onReset: () => void;
}) {
  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [state, setState] = useState<EditorState>({ kind: "idle" });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setState({ kind: "loading" });
    setError(null);
    getTemplate(template.id)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        setDraft(d.effective_prompt);
        setState({ kind: "idle" });
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("template detail failed", err);
        setError("Vorlage konnte nicht geladen werden.");
        setState({ kind: "idle" });
      });
    return () => {
      cancelled = true;
    };
  }, [open, template.id]);

  async function handleSave() {
    if (!detail) return;
    if (draft.trim().length < 10) {
      setError("Der System-Prompt muss mindestens 10 Zeichen lang sein.");
      return;
    }
    setState({ kind: "saving" });
    setError(null);
    try {
      await updateTemplatePrompt(template.id, draft);
      const refreshed = await getTemplate(template.id);
      setDetail(refreshed);
      setDraft(refreshed.effective_prompt);
      onSaved();
    } catch (err) {
      console.error("save prompt failed", err);
      setError("Speichern fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setState({ kind: "idle" });
    }
  }

  async function handleReset() {
    if (!detail) return;
    setState({ kind: "resetting" });
    setError(null);
    try {
      await resetTemplatePrompt(template.id);
      const refreshed = await getTemplate(template.id);
      setDetail(refreshed);
      setDraft(refreshed.effective_prompt);
      onReset();
    } catch (err) {
      console.error("reset prompt failed", err);
      setError("Zurücksetzen fehlgeschlagen.");
    } finally {
      setState({ kind: "idle" });
    }
  }

  const dirty = detail !== null && draft.trim() !== detail.effective_prompt.trim();

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition hover:bg-surface-soft"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-2">
            <p className="font-medium text-text-primary">{template.name}</p>
            {template.is_customized && (
              <span
                className="mono text-[0.6875rem] uppercase tracking-[0.08em]"
                style={{ color: "var(--gold-deep)" }}
              >
                · angepasst
              </span>
            )}
          </div>
          {template.description && (
            <p className="mt-1 text-sm text-text-secondary">{template.description}</p>
          )}
        </div>
        <span
          className="mono text-xs text-text-meta"
          aria-hidden
        >
          {open ? "▾" : "▸"}
        </span>
      </button>

      {open && (
        <div className="border-t border-border-subtle px-5 py-5">
          {state.kind === "loading" && (
            <div className="space-y-2">
              <div className="h-4 w-1/4 animate-pulse rounded bg-surface-soft" />
              <div className="h-40 animate-pulse rounded bg-surface-soft" />
            </div>
          )}

          {state.kind !== "loading" && detail && (
            <>
              <label className="block">
                <span className="block text-sm font-medium text-text-primary">
                  System-Prompt
                </span>
                <span className="mt-1 mb-2 block text-xs text-text-secondary">
                  Anweisungen, die das Sprachmodell für jede Zusammenfassung
                  in dieser Vorlage erhält. Variablen wie das Transkript
                  werden vom System automatisch ergänzt.
                </span>
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  className="input w-full font-mono text-[0.8125rem] leading-relaxed"
                  rows={12}
                  spellCheck={false}
                  disabled={state.kind === "saving" || state.kind === "resetting"}
                />
              </label>

              {error && (
                <p className="mt-3 text-sm" style={{ color: "var(--error)" }}>
                  {error}
                </p>
              )}

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs text-text-meta">
                  {detail.is_customized && detail.custom_updated_at ? (
                    <>
                      Angepasst am{" "}
                      {new Date(detail.custom_updated_at).toLocaleString("de-DE", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </>
                  ) : (
                    <>Standard-Vorlage (noch nicht angepasst)</>
                  )}
                </div>
                <div className="flex gap-2">
                  {detail.is_customized && (
                    <button
                      type="button"
                      onClick={handleReset}
                      className="btn-tertiary"
                      disabled={
                        state.kind === "saving" || state.kind === "resetting"
                      }
                    >
                      {state.kind === "resetting"
                        ? "Wird zurückgesetzt…"
                        : "Auf Standard zurücksetzen"}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleSave}
                    className="btn-primary"
                    disabled={
                      !dirty ||
                      state.kind === "saving" ||
                      state.kind === "resetting"
                    }
                  >
                    {state.kind === "saving" ? "Wird gespeichert…" : "Speichern"}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
