"use client";

import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import {
  createTemplate,
  deleteTemplate,
  getTemplate,
  listTemplates,
  resetTemplatePrompt,
  updateTemplate,
  updateTemplatePrompt,
  type CustomField,
  type CustomFieldType,
  type TemplateDetail,
  type TemplateDto,
  type TemplatePayload,
} from "@/lib/api/templates";

type EditorState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "saving" }
  | { kind: "resetting" }
  | { kind: "deleting" };

const PROMPT_PLACEHOLDER = `Du bist ein professioneller Protokollführer.

Analysiere das folgende Meeting-Transkript und gib eine strukturierte
JSON-Antwort zurück:
- zusammenfassung: ein kurzer Fließtext
- kernpunkte: zentrale Themen als Liste
- entscheidungen: getroffene Beschlüsse
- aufgaben: To-dos mit "was", "wer", "wann"
- offene_fragen: was unbeantwortet blieb`;

export function TemplatePrompts() {
  const [list, setList] = useState<TemplateDto[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const toast = useToast();

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
    listTemplates()
      .then((tpls) => setList(tpls))
      .catch(() => {});
  }

  if (list === null) {
    return (
      <div className="space-y-2">
        <div className="h-14 animate-pulse rounded bg-surface-soft" />
        <div className="h-14 animate-pulse rounded bg-surface-soft" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        {!showCreate && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="btn-secondary inline-flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            Neue Vorlage
          </button>
        )}
      </div>

      {showCreate && (
        <CreateTemplateForm
          onCreated={(t) => {
            setShowCreate(false);
            refreshList();
            setOpenId(t.id);
            toast.show({
              message: `Vorlage „${t.name}" angelegt.`,
              variant: "success",
            });
          }}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {list.length === 0 ? (
        <p className="text-sm text-text-secondary">
          Keine Vorlagen vorhanden. Legen Sie über „Neue Vorlage" Ihre erste an.
        </p>
      ) : (
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
              onDeleted={() => {
                setOpenId(null);
                refreshList();
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Create form ──────────────────────────────────────────────────────

function CreateTemplateForm({
  onCreated,
  onCancel,
}: {
  onCreated: (t: TemplateDto) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    if (name.trim().length === 0) {
      setError("Bitte einen Namen vergeben.");
      return;
    }
    if (prompt.trim().length < 10) {
      setError("Der System-Prompt muss mindestens 10 Zeichen lang sein.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const t = await createTemplate({
        name: name.trim(),
        description: description.trim(),
        system_prompt: prompt.trim(),
      });
      onCreated(t);
    } catch (err) {
      console.error("create template failed", err);
      setError("Anlegen fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-border-strong bg-white p-5"
    >
      <div className="flex items-baseline justify-between">
        <p className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
          Neue Vorlage
        </p>
      </div>

      <label className="block">
        <span className="block text-sm font-medium text-text-primary">Name</span>
        <input
          type="text"
          className="input mt-1 w-full"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="z. B. Retrospektive"
          maxLength={120}
          autoFocus
          disabled={saving}
        />
      </label>

      <label className="block">
        <span className="block text-sm font-medium text-text-primary">
          Beschreibung
        </span>
        <span className="mt-1 mb-2 block text-xs text-text-secondary">
          Wofür Sie diese Vorlage nutzen — wird in der Aufnahme-Auswahl
          angezeigt.
        </span>
        <input
          type="text"
          className="input w-full"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="z. B. Sprint-Rückblick mit Action-Items"
          maxLength={500}
          disabled={saving}
        />
      </label>

      <label className="block">
        <span className="block text-sm font-medium text-text-primary">
          System-Prompt
        </span>
        <span className="mt-1 mb-2 block text-xs text-text-secondary">
          Anweisungen ans Sprachmodell, wie das Transkript zu strukturieren
          ist. Neue Vorlagen nutzen automatisch ein flexibles Standard-Schema
          (Zusammenfassung · Kernpunkte · Entscheidungen · Aufgaben · Offene Fragen).
        </span>
        <textarea
          className="input w-full font-mono text-[0.8125rem] leading-relaxed"
          rows={10}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={PROMPT_PLACEHOLDER}
          spellCheck={false}
          disabled={saving}
        />
      </label>

      {error && (
        <p className="text-sm" style={{ color: "var(--error)" }}>
          {error}
        </p>
      )}

      <div className="flex flex-wrap justify-end gap-2 border-t border-border-subtle pt-4">
        <button
          type="button"
          onClick={onCancel}
          className="btn-tertiary"
          disabled={saving}
        >
          Abbrechen
        </button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Wird angelegt …" : "Vorlage anlegen"}
        </button>
      </div>
    </form>
  );
}

// ─── Template row ─────────────────────────────────────────────────────

function TemplateRow({
  template,
  open,
  onToggle,
  onSaved,
  onReset,
  onDeleted,
}: {
  template: TemplateDto;
  open: boolean;
  onToggle: () => void;
  onSaved: () => void;
  onReset: () => void;
  onDeleted: () => void;
}) {
  const toast = useToast();
  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [draft, setDraft] = useState<string>("");
  const [customFields, setCustomFields] = useState<CustomField[]>([]);
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
        setName(d.name);
        setDescription(d.description ?? "");
        setDraft(d.effective_prompt);
        setCustomFields(d.custom_fields ?? []);
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

  // Org templates: full edit (name/description/prompt + delete)
  const isOrgOwned = !template.is_system;

  const dirty =
    detail !== null &&
    (draft.trim() !== detail.effective_prompt.trim() ||
      name.trim() !== (detail.name ?? "") ||
      (description ?? "").trim() !== (detail.description ?? "") ||
      JSON.stringify(customFields) !==
        JSON.stringify(detail.custom_fields ?? []));

  async function handleSave() {
    if (!detail) return;
    if (draft.trim().length < 10) {
      setError("Der System-Prompt muss mindestens 10 Zeichen lang sein.");
      return;
    }
    if (name.trim().length === 0) {
      setError("Bitte einen Namen vergeben.");
      return;
    }
    // Validate custom fields: names need to be unique + match snake_case.
    const namePattern = /^[a-z][a-z0-9_]*$/;
    const seen = new Set<string>();
    for (const cf of customFields) {
      if (!namePattern.test(cf.name)) {
        setError(
          `Feldname „${cf.name}" ungültig — nur Kleinbuchstaben, Ziffern und _ erlaubt (z. B. "geburtsdatum").`,
        );
        return;
      }
      if (seen.has(cf.name)) {
        setError(`Feldname „${cf.name}" doppelt.`);
        return;
      }
      seen.add(cf.name);
      if (!cf.label.trim()) {
        setError(`Feld „${cf.name}" hat keine Bezeichnung.`);
        return;
      }
    }
    setState({ kind: "saving" });
    setError(null);
    try {
      if (isOrgOwned) {
        const payload: TemplatePayload = {
          name: name.trim(),
          description: description.trim(),
          system_prompt: draft.trim(),
        };
        await updateTemplate(template.id, payload);
      } else {
        // System template: send display overrides only if changed from
        // the original default. Empty string == "clear override and
        // fall back to default".
        const newName = name.trim();
        const newDesc = description.trim();
        const defaultName = detail.default_name ?? detail.name;
        const defaultDesc = detail.default_description ?? detail.description ?? "";
        await updateTemplatePrompt(
          template.id,
          draft,
          newName === defaultName ? "" : newName,
          newDesc === defaultDesc ? "" : newDesc,
          customFields,
        );
      }
      const refreshed = await getTemplate(template.id);
      setDetail(refreshed);
      setName(refreshed.name);
      setDescription(refreshed.description ?? "");
      setDraft(refreshed.effective_prompt);
      setCustomFields(refreshed.custom_fields ?? []);
      onSaved();
      toast.show({
        message: `„${refreshed.name}" gespeichert.`,
        variant: "success",
      });
    } catch (err) {
      console.error("save template failed", err);
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

  function handleDeleteRequest() {
    if (!isOrgOwned || !detail) return;
    const name = detail.name;
    let cancelled = false;

    toast.show({
      message: `Vorlage „${name}" wird gelöscht`,
      variant: "undo",
      duration: 5000,
      action: {
        label: "Rückgängig",
        onClick: () => {
          cancelled = true;
        },
      },
      onTimeout: async () => {
        if (cancelled) return;
        setState({ kind: "deleting" });
        try {
          await deleteTemplate(template.id);
          onDeleted();
        } catch (err) {
          console.error("delete template failed", err);
          toast.show({
            message: "Löschen fehlgeschlagen. Bitte erneut versuchen.",
            variant: "error",
          });
          setState({ kind: "idle" });
        }
      },
    });
  }

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
            {template.is_system && (
              <span className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
                · system
              </span>
            )}
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
        <span className="mono text-xs text-text-meta" aria-hidden>
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
              <div className="space-y-4">
                <label className="block">
                  <span className="block text-sm font-medium text-text-primary">
                    Name
                  </span>
                  {!isOrgOwned && detail?.default_name && (
                    <span className="mt-0.5 block text-xs text-text-meta">
                      Standardname: <span className="font-mono">{detail.default_name}</span>
                      {detail.display_name && (
                        <button
                          type="button"
                          onClick={() => setName(detail.default_name ?? "")}
                          className="ml-2 underline hover:text-text-primary"
                        >
                          Auf Standard zurücksetzen
                        </button>
                      )}
                    </span>
                  )}
                  <input
                    type="text"
                    className="input mt-1 w-full"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    maxLength={120}
                    disabled={
                      state.kind === "saving" || state.kind === "deleting"
                    }
                  />
                </label>
                <label className="block">
                  <span className="block text-sm font-medium text-text-primary">
                    Beschreibung
                  </span>
                  {!isOrgOwned && detail?.default_description && (
                    <span className="mt-0.5 block text-xs text-text-meta">
                      Standardbeschreibung: {detail.default_description}
                    </span>
                  )}
                  <input
                    type="text"
                    className="input mt-1 w-full"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    maxLength={500}
                    disabled={
                      state.kind === "saving" || state.kind === "deleting"
                    }
                  />
                </label>
                {!isOrgOwned && (
                  <div className="rounded-md bg-surface-soft px-3 py-2 text-xs text-text-secondary">
                    Diese Werksvorlage hat ein festes Output-Schema und
                    feste Felder in der Zusammenfassung. Sie können den
                    Namen, die Beschreibung und den System-Prompt für
                    Ihre Organisation anpassen.
                  </div>
                )}
              </div>

              <label className="mt-4 block">
                <span className="block text-sm font-medium text-text-primary">
                  System-Prompt
                </span>
                <span className="mt-1 mb-2 block text-xs text-text-secondary">
                  Anweisungen ans Sprachmodell. Variablen wie das Transkript
                  ergänzt das System automatisch. Diese Vorlage ist für
                  Qwen 2.5 optimiert (Markdown-Sektionen, Schema-Echo,
                  Few-Shot-Beispiel).
                </span>
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  className="input w-full font-mono text-[0.8125rem] leading-relaxed"
                  rows={12}
                  spellCheck={false}
                  disabled={state.kind === "saving" || state.kind === "resetting" || state.kind === "deleting"}
                />
              </label>

              {!isOrgOwned && (
                <CustomFieldsEditor
                  fields={customFields}
                  onChange={setCustomFields}
                  disabled={state.kind !== "idle"}
                />
              )}

              {detail.few_shot_input && detail.few_shot_output && (
                <details className="mt-4 rounded-md border border-border-subtle bg-surface-soft p-3 text-xs">
                  <summary className="cursor-pointer select-none font-medium text-text-primary">
                    Few-Shot-Beispiel (read-only)
                  </summary>
                  <p className="mt-2 text-text-secondary">
                    Insilo schickt vor jedem echten Transkript dieses
                    Beispiel an die KI, damit sie das Antwortformat
                    sicher trifft. Es kann aktuell nur am Werks-Template
                    geändert werden — Customizing erfolgt rein über den
                    System-Prompt.
                  </p>
                  <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div>
                      <p className="mono text-[0.625rem] uppercase tracking-[0.08em] text-text-meta">
                        Eingabe-Snippet
                      </p>
                      <pre className="mt-1 max-h-[200px] overflow-auto rounded bg-white p-2 font-mono text-[0.75rem] text-text-primary">
                        {detail.few_shot_input}
                      </pre>
                    </div>
                    <div>
                      <p className="mono text-[0.625rem] uppercase tracking-[0.08em] text-text-meta">
                        Erwartete JSON-Antwort
                      </p>
                      <pre className="mt-1 max-h-[200px] overflow-auto rounded bg-white p-2 font-mono text-[0.75rem] text-text-primary">
                        {JSON.stringify(detail.few_shot_output, null, 2)}
                      </pre>
                    </div>
                  </div>
                </details>
              )}

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
                  ) : isOrgOwned ? (
                    <>Version {detail.version}</>
                  ) : (
                    <>Werksvorlage (noch nicht angepasst)</>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {isOrgOwned && (
                    <button
                      type="button"
                      onClick={handleDeleteRequest}
                      className="btn-tertiary inline-flex items-center gap-1.5"
                      style={{ color: "var(--error)" }}
                      disabled={
                        state.kind === "saving" || state.kind === "deleting"
                      }
                    >
                      <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                      Vorlage löschen
                    </button>
                  )}
                  {!isOrgOwned && detail.is_customized && (
                    <button
                      type="button"
                      onClick={handleReset}
                      className="btn-tertiary"
                      disabled={
                        state.kind === "saving" || state.kind === "resetting"
                      }
                    >
                      {state.kind === "resetting"
                        ? "Wird zurückgesetzt …"
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
                      state.kind === "resetting" ||
                      state.kind === "deleting"
                    }
                  >
                    {state.kind === "saving" ? "Wird gespeichert …" : "Speichern"}
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

// ─── Custom-Fields-Editor (v0.1.41 Lite-Schema-Editor) ────────────────

const TYPE_LABEL: Record<CustomFieldType, string> = {
  string: "Text",
  array_string: "Liste von Text",
};

function CustomFieldsEditor({
  fields,
  onChange,
  disabled,
}: {
  fields: CustomField[];
  onChange: (next: CustomField[]) => void;
  disabled?: boolean;
}) {
  function update(idx: number, patch: Partial<CustomField>) {
    onChange(
      fields.map((cf, i) => (i === idx ? { ...cf, ...patch } : cf)),
    );
  }

  function remove(idx: number) {
    onChange(fields.filter((_, i) => i !== idx));
  }

  function add() {
    onChange([
      ...fields,
      { name: "", label: "", type: "string", description: "" },
    ]);
  }

  return (
    <section className="mt-6 rounded-md border border-border-subtle bg-surface-soft p-4">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-text-primary">
            Zusätzliche Felder
          </p>
          <p className="mt-0.5 text-xs text-text-secondary">
            Ergänzen Sie eigene Felder zur Zusammenfassung — z.&nbsp;B.
            „Geburtsdatum", „Zeugen", „Aktenzeichen". Die KI füllt sie
            zusammen mit den Standard-Feldern. Bestehende Standard-Felder
            werden dadurch nicht überschrieben.
          </p>
        </div>
        <button
          type="button"
          onClick={add}
          className="btn-tertiary inline-flex items-center gap-1.5"
          disabled={disabled}
        >
          <Plus className="h-3.5 w-3.5" strokeWidth={2} />
          Feld hinzufügen
        </button>
      </header>

      {fields.length === 0 && (
        <p className="text-xs text-text-meta">
          Noch keine zusätzlichen Felder.
        </p>
      )}

      <div className="space-y-3">
        {fields.map((cf, idx) => (
          <div
            key={idx}
            className="rounded-md border border-border-subtle bg-white p-3"
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <label className="block">
                <span className="block text-xs font-medium text-text-secondary">
                  Feldname (intern)
                </span>
                <input
                  type="text"
                  value={cf.name}
                  onChange={(e) =>
                    update(idx, {
                      name: e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9_]/g, "_")
                        .replace(/_+/g, "_"),
                    })
                  }
                  placeholder="geburtsdatum"
                  maxLength={64}
                  className="input mt-1 w-full font-mono text-[0.8125rem]"
                  disabled={disabled}
                />
              </label>
              <label className="block">
                <span className="block text-xs font-medium text-text-secondary">
                  Bezeichnung (Anzeige)
                </span>
                <input
                  type="text"
                  value={cf.label}
                  onChange={(e) => update(idx, { label: e.target.value })}
                  placeholder="Geburtsdatum"
                  maxLength={120}
                  className="input mt-1 w-full"
                  disabled={disabled}
                />
              </label>
            </div>

            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <label className="block">
                <span className="block text-xs font-medium text-text-secondary">
                  Typ
                </span>
                <select
                  value={cf.type}
                  onChange={(e) =>
                    update(idx, { type: e.target.value as CustomFieldType })
                  }
                  className="input mt-1 w-full"
                  disabled={disabled}
                >
                  {(Object.keys(TYPE_LABEL) as CustomFieldType[]).map((t) => (
                    <option key={t} value={t}>
                      {TYPE_LABEL[t]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="block text-xs font-medium text-text-secondary">
                  Hinweis an die KI (optional)
                </span>
                <input
                  type="text"
                  value={cf.description}
                  onChange={(e) => update(idx, { description: e.target.value })}
                  placeholder="z. B. TT.MM.JJJJ falls genannt"
                  maxLength={500}
                  className="input mt-1 w-full"
                  disabled={disabled}
                />
              </label>
            </div>

            <div className="mt-2 flex justify-end">
              <button
                type="button"
                onClick={() => remove(idx)}
                className="btn-tertiary inline-flex items-center gap-1 text-xs"
                style={{ color: "var(--error)" }}
                disabled={disabled}
              >
                <Trash2 className="h-3 w-3" strokeWidth={1.75} />
                Feld entfernen
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
