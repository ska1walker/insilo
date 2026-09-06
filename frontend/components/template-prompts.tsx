"use client";

import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import {
  createTemplate,
  deleteTemplate,
  getTemplate,
  listTemplates,
  LOCALES,
  resetTemplatePrompt,
  updateTemplate,
  updateTemplatePrompt,
  type CustomField,
  type CustomFieldType,
  type Locale,
  type LocalePromptMap,
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

/** Build an empty drafts map seeded from a TemplateDetail's effective prompts. */
function draftsFrom(detail: TemplateDetail): Record<Locale, string> {
  const out = {} as Record<Locale, string>;
  for (const loc of LOCALES) {
    out[loc] = detail.effective_prompts[loc] ?? "";
  }
  return out;
}

/** Build an empty drafts map (all locales → ""). */
function emptyDrafts(): Record<Locale, string> {
  const out = {} as Record<Locale, string>;
  for (const loc of LOCALES) out[loc] = "";
  return out;
}

/** Strip empty entries — backend falls back to DE for missing locales. */
function compactDrafts(drafts: Record<Locale, string>): LocalePromptMap {
  const out: LocalePromptMap = {};
  for (const loc of LOCALES) {
    const v = drafts[loc]?.trim();
    if (v) out[loc] = v;
  }
  return out;
}

export function TemplatePrompts() {
  const t = useTranslations("templatePrompts");
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
        <div className="h-14 rounded bg-flaeche-3" />
        <div className="h-14 rounded bg-flaeche-3" />
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
            className="btn btn-sekundaer inline-flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            {t("newTemplate")}
          </button>
        )}
      </div>

      {showCreate && (
        <CreateTemplateForm
          onCreated={(created) => {
            setShowCreate(false);
            refreshList();
            setOpenId(created.id);
            toast.show({
              message: t("createdToast", { name: created.name }),
              variant: "success",
            });
          }}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {list.length === 0 ? (
        <p className="text-sm text-text-sekundaer">{t("noneYet")}</p>
      ) : (
        <div className="divide-y divide-trennlinie rounded-lg border border-trennlinie bg-seite">
          {list.map((tpl) => (
            <TemplateRow
              key={tpl.id}
              template={tpl}
              open={openId === tpl.id}
              onToggle={() => setOpenId(openId === tpl.id ? null : tpl.id)}
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

// ─── Locale tab strip ─────────────────────────────────────────────────

function LocaleTabs({
  active,
  onChange,
  drafts,
}: {
  active: Locale;
  onChange: (loc: Locale) => void;
  drafts: Record<Locale, string>;
}) {
  const tLocale = useTranslations("locale.names");
  return (
    <div
      role="tablist"
      aria-label="Locale"
      className="flex flex-wrap gap-1 border-b border-trennlinie"
    >
      {LOCALES.map((loc) => {
        const isActive = loc === active;
        const isEmpty = !drafts[loc]?.trim();
        return (
          <button
            key={loc}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(loc)}
            className={
              "relative -mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-1.5 text-xs font-medium transition " +
              (isActive
                ? "border-rand-betont text-text-primaer"
                : "border-transparent text-text-gedaempft hover:text-text-primaer")
            }
            title={tLocale(loc)}
          >
            <span className="mono uppercase tracking-[0.08em]">{loc}</span>
            {isEmpty && loc !== "de" && (
              <span
                aria-hidden
                className="inline-block h-1 w-1 rounded-full bg-text-gedaempft opacity-50"
              />
            )}
          </button>
        );
      })}
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
  const t = useTranslations("templatePrompts");
  const tCommon = useTranslations("common");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [drafts, setDrafts] = useState<Record<Locale, string>>(emptyDrafts());
  const [activeLocale, setActiveLocale] = useState<Locale>("de");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    if (name.trim().length === 0) {
      setError(t("errEmptyName"));
      return;
    }
    const dePrompt = drafts.de.trim();
    if (dePrompt.length < 10) {
      setError(t("errPromptTooShort"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createTemplate({
        name: name.trim(),
        description: description.trim(),
        system_prompts: compactDrafts(drafts),
      });
      onCreated(created);
    } catch (err) {
      console.error("create template failed", err);
      setError(t("errCreate"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-lg border border-rand-betont bg-seite p-5"
    >
      <div className="flex items-baseline justify-between">
        <p className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-gedaempft">
          {t("createHeader")}
        </p>
      </div>

      <label className="block">
        <span className="block text-sm font-medium text-text-primaer">{t("nameLabel")}</span>
        <input
          type="text"
          className="input mt-1 w-full"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("namePlaceholder")}
          maxLength={120}
          autoFocus
          disabled={saving}
        />
      </label>

      <label className="block">
        <span className="block text-sm font-medium text-text-primaer">
          {t("descLabel")}
        </span>
        <span className="mt-1 mb-2 block text-xs text-text-sekundaer">
          {t("descHint")}
        </span>
        <input
          type="text"
          className="input w-full"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("descPlaceholder")}
          maxLength={500}
          disabled={saving}
        />
      </label>

      <div>
        <span className="block text-sm font-medium text-text-primaer">
          {t("promptLabel")}
        </span>
        <span className="mt-1 mb-2 block text-xs text-text-sekundaer">
          {t("promptHintCreate")}
        </span>
        <span className="mb-2 block text-xs text-text-gedaempft">
          {t("localeHint")}
        </span>
        <LocaleTabs
          active={activeLocale}
          onChange={setActiveLocale}
          drafts={drafts}
        />
        <textarea
          className="input mt-3 w-full font-mono text-[0.8125rem] leading-relaxed"
          rows={10}
          value={drafts[activeLocale]}
          onChange={(e) =>
            setDrafts((prev) => ({ ...prev, [activeLocale]: e.target.value }))
          }
          placeholder={
            activeLocale === "de"
              ? PROMPT_PLACEHOLDER
              : t("placeholderFallback")
          }
          spellCheck={false}
          disabled={saving}
        />
      </div>

      {error && (
        <p className="text-sm" style={{ color: "var(--am-fehler)" }}>
          {error}
        </p>
      )}

      <div className="flex flex-wrap justify-end gap-2 border-t border-trennlinie pt-4">
        <button
          type="button"
          onClick={onCancel}
          className="btn btn-still"
          disabled={saving}
        >
          {tCommon("cancel")}
        </button>
        <button type="submit" className="btn btn-primaer" disabled={saving}>
          {saving ? t("creating") : t("createBtn")}
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
  const t = useTranslations("templatePrompts");
  const tCommon = useTranslations("common");
  const toast = useToast();
  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [drafts, setDrafts] = useState<Record<Locale, string>>(emptyDrafts());
  const [activeLocale, setActiveLocale] = useState<Locale>("de");
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
        setDrafts(draftsFrom(d));
        setActiveLocale("de");
        setCustomFields(d.custom_fields ?? []);
        setState({ kind: "idle" });
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("template detail failed", err);
        setError(t("errLoad"));
        setState({ kind: "idle" });
      });
    return () => {
      cancelled = true;
    };
  }, [open, template.id, t]);

  // Org templates: full edit (name/description/prompt + delete)
  const isOrgOwned = !template.is_system;

  // Drafts differ from the persisted effective prompts when any locale's
  // text has changed — compare trimmed strings per locale.
  const promptsDirty =
    detail !== null &&
    LOCALES.some(
      (loc) =>
        (drafts[loc] ?? "").trim() !==
        (detail.effective_prompts[loc] ?? "").trim(),
    );
  const dirty =
    detail !== null &&
    (promptsDirty ||
      name.trim() !== (detail.name ?? "") ||
      (description ?? "").trim() !== (detail.description ?? "") ||
      JSON.stringify(customFields) !==
        JSON.stringify(detail.custom_fields ?? []));

  async function handleSave() {
    if (!detail) return;
    if (drafts.de.trim().length < 10) {
      // DE is the canonical fallback — enforce minimum length only on DE.
      setActiveLocale("de");
      setError(t("errPromptTooShort"));
      return;
    }
    if (name.trim().length === 0) {
      setError(t("errEmptyName"));
      return;
    }
    // Validate custom fields: names need to be unique + match snake_case.
    const namePattern = /^[a-z][a-z0-9_]*$/;
    const seen = new Set<string>();
    for (const cf of customFields) {
      if (!namePattern.test(cf.name)) {
        setError(t("errFieldInvalid", { name: cf.name }));
        return;
      }
      if (seen.has(cf.name)) {
        setError(t("errFieldDuplicate", { name: cf.name }));
        return;
      }
      seen.add(cf.name);
      if (!cf.label.trim()) {
        setError(t("errFieldNoLabel", { name: cf.name }));
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
          system_prompts: compactDrafts(drafts),
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
          compactDrafts(drafts),
          newName === defaultName ? "" : newName,
          newDesc === defaultDesc ? "" : newDesc,
          customFields,
        );
      }
      const refreshed = await getTemplate(template.id);
      setDetail(refreshed);
      setName(refreshed.name);
      setDescription(refreshed.description ?? "");
      setDrafts(draftsFrom(refreshed));
      setCustomFields(refreshed.custom_fields ?? []);
      onSaved();
      toast.show({
        message: t("savedToast", { name: refreshed.name }),
        variant: "success",
      });
    } catch (err) {
      console.error("save template failed", err);
      setError(t("errSave"));
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
      setDrafts(draftsFrom(refreshed));
      onReset();
    } catch (err) {
      console.error("reset prompt failed", err);
      setError(t("errReset"));
    } finally {
      setState({ kind: "idle" });
    }
  }

  /** Pull every visible locale back to its default-prompt baseline. */
  function handleResetDraftsToDefault() {
    if (!detail) return;
    const next = {} as Record<Locale, string>;
    for (const loc of LOCALES) {
      next[loc] = detail.default_prompts[loc] ?? "";
    }
    setDrafts(next);
  }

  function handleDeleteRequest() {
    if (!isOrgOwned || !detail) return;
    const detailName = detail.name;
    let cancelled = false;

    toast.show({
      message: t("deleteUndoMsg", { name: detailName }),
      variant: "undo",
      duration: 5000,
      action: {
        label: tCommon("undo"),
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
            message: t("deleteFailToast"),
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
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition hover:bg-flaeche-1"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-2">
            <p className="font-medium text-text-primaer">{template.name}</p>
            {template.is_system && (
              <span className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-gedaempft">
                {t("tagSystem")}
              </span>
            )}
            {template.is_customized && (
              <span
                className="mono text-[0.6875rem] uppercase tracking-[0.08em]"
                style={{ color: "var(--am-gold-beschriftung)" }}
              >
                {t("tagCustomized")}
              </span>
            )}
          </div>
          {template.description && (
            <p className="mt-1 text-sm text-text-sekundaer">{template.description}</p>
          )}
        </div>
        <span className="mono text-xs text-text-gedaempft" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>

      {open && (
        <div className="border-t border-trennlinie px-5 py-5">
          {state.kind === "loading" && (
            <div className="space-y-2">
              <div className="h-4 w-1/4 rounded bg-flaeche-3" />
              <div className="h-40 rounded bg-flaeche-3" />
            </div>
          )}

          {state.kind !== "loading" && detail && (
            <>
              <div className="space-y-4">
                <label className="block">
                  <span className="block text-sm font-medium text-text-primaer">
                    {t("nameLabel")}
                  </span>
                  {!isOrgOwned && detail?.default_name && (
                    <span className="mt-0.5 block text-xs text-text-gedaempft">
                      {t("defaultName")}{" "}
                      <span className="font-mono">{detail.default_name}</span>
                      {detail.display_name && (
                        <button
                          type="button"
                          onClick={() => setName(detail.default_name ?? "")}
                          className="ml-2 underline hover:text-text-primaer"
                        >
                          {t("resetToDefaultLink")}
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
                  <span className="block text-sm font-medium text-text-primaer">
                    {t("descLabel")}
                  </span>
                  {!isOrgOwned && detail?.default_description && (
                    <span className="mt-0.5 block text-xs text-text-gedaempft">
                      {t("defaultDesc", { value: detail.default_description })}
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
                  <div className="rounded-md bg-flaeche-1 px-3 py-2 text-xs text-text-sekundaer">
                    {t("systemNote")}
                  </div>
                )}
              </div>

              <div className="mt-4">
                <span className="block text-sm font-medium text-text-primaer">
                  {t("promptLabel")}
                </span>
                <span className="mt-1 mb-2 block text-xs text-text-sekundaer">
                  {t("promptHintEdit")}
                </span>
                <span className="mb-2 block text-xs text-text-gedaempft">
                  {t("localeHint")}
                </span>
                <LocaleTabs
                  active={activeLocale}
                  onChange={setActiveLocale}
                  drafts={drafts}
                />
                <textarea
                  value={drafts[activeLocale]}
                  onChange={(e) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [activeLocale]: e.target.value,
                    }))
                  }
                  className="input mt-3 w-full font-mono text-[0.8125rem] leading-relaxed"
                  rows={12}
                  spellCheck={false}
                  placeholder={
                    activeLocale === "de"
                      ? undefined
                      : t("placeholderFallback")
                  }
                  disabled={
                    state.kind === "saving" ||
                    state.kind === "resetting" ||
                    state.kind === "deleting"
                  }
                />
              </div>

              {!isOrgOwned && (
                <CustomFieldsEditor
                  fields={customFields}
                  onChange={setCustomFields}
                  disabled={state.kind !== "idle"}
                />
              )}

              {detail.few_shot_input && detail.few_shot_output && (
                <details className="mt-4 rounded-md border border-trennlinie bg-flaeche-1 p-3 text-xs">
                  <summary className="cursor-pointer select-none font-medium text-text-primaer">
                    {t("fewShotTitle")}
                  </summary>
                  <p className="mt-2 text-text-sekundaer">
                    {t("fewShotIntro")}
                  </p>
                  <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div>
                      <p className="mono text-[0.625rem] uppercase tracking-[0.08em] text-text-gedaempft">
                        {t("fewShotInput")}
                      </p>
                      <pre className="mt-1 max-h-[200px] overflow-auto rounded bg-seite p-2 font-mono text-[0.75rem] text-text-primaer">
                        {detail.few_shot_input}
                      </pre>
                    </div>
                    <div>
                      <p className="mono text-[0.625rem] uppercase tracking-[0.08em] text-text-gedaempft">
                        {t("fewShotOutput")}
                      </p>
                      <pre className="mt-1 max-h-[200px] overflow-auto rounded bg-seite p-2 font-mono text-[0.75rem] text-text-primaer">
                        {JSON.stringify(detail.few_shot_output, null, 2)}
                      </pre>
                    </div>
                  </div>
                </details>
              )}

              {error && (
                <p className="mt-3 text-sm" style={{ color: "var(--am-fehler)" }}>
                  {error}
                </p>
              )}

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs text-text-gedaempft">
                  {detail.is_customized && detail.custom_updated_at ? (
                    <>
                      {t("customizedAt", {
                        date: new Date(detail.custom_updated_at).toLocaleString(
                          "de-DE",
                          {
                            dateStyle: "medium",
                            timeStyle: "short",
                          },
                        ),
                      })}
                    </>
                  ) : isOrgOwned ? (
                    <>{t("version", { version: detail.version })}</>
                  ) : (
                    <>{t("factoryNotCustomized")}</>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {isOrgOwned && (
                    <button
                      type="button"
                      onClick={handleDeleteRequest}
                      className="btn btn-still inline-flex items-center gap-1.5"
                      style={{ color: "var(--am-fehler)" }}
                      disabled={
                        state.kind === "saving" || state.kind === "deleting"
                      }
                    >
                      <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                      {t("deleteBtn")}
                    </button>
                  )}
                  {!isOrgOwned && detail.is_customized && (
                    <button
                      type="button"
                      onClick={handleReset}
                      className="btn btn-still"
                      disabled={
                        state.kind === "saving" || state.kind === "resetting"
                      }
                    >
                      {state.kind === "resetting"
                        ? t("resetting")
                        : t("resetToDefault")}
                    </button>
                  )}
                  {!isOrgOwned && !detail.is_customized && promptsDirty && (
                    <button
                      type="button"
                      onClick={handleResetDraftsToDefault}
                      className="btn btn-still"
                      disabled={state.kind !== "idle"}
                    >
                      {t("revertDrafts")}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleSave}
                    className="btn btn-primaer"
                    disabled={
                      !dirty ||
                      state.kind === "saving" ||
                      state.kind === "resetting" ||
                      state.kind === "deleting"
                    }
                  >
                    {state.kind === "saving" ? t("savingBtn") : t("saveBtn")}
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

function CustomFieldsEditor({
  fields,
  onChange,
  disabled,
}: {
  fields: CustomField[];
  onChange: (next: CustomField[]) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("templatePrompts.customFields");

  const TYPE_LABEL: Record<CustomFieldType, string> = {
    string: t("types.string"),
    array_string: t("types.array_string"),
  };

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
    <section className="mt-6 rounded-md border border-trennlinie bg-flaeche-1 p-4">
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-text-primaer">
            {t("title")}
          </p>
          <p className="mt-0.5 text-xs text-text-sekundaer">
            {t("hint")}
          </p>
        </div>
        <button
          type="button"
          onClick={add}
          className="btn btn-still inline-flex items-center gap-1.5"
          disabled={disabled}
        >
          <Plus className="h-3.5 w-3.5" strokeWidth={2} />
          {t("addBtn")}
        </button>
      </header>

      {fields.length === 0 && (
        <p className="text-xs text-text-gedaempft">
          {t("none")}
        </p>
      )}

      <div className="space-y-3">
        {fields.map((cf, idx) => (
          <div
            key={idx}
            className="rounded-md border border-trennlinie bg-seite p-3"
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <label className="block">
                <span className="block text-xs font-medium text-text-sekundaer">
                  {t("internalName")}
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
                  placeholder={t("internalPlaceholder")}
                  maxLength={64}
                  className="input mt-1 w-full font-mono text-[0.8125rem]"
                  disabled={disabled}
                />
              </label>
              <label className="block">
                <span className="block text-xs font-medium text-text-sekundaer">
                  {t("labelLabel")}
                </span>
                <input
                  type="text"
                  value={cf.label}
                  onChange={(e) => update(idx, { label: e.target.value })}
                  placeholder={t("labelPlaceholder")}
                  maxLength={120}
                  className="input mt-1 w-full"
                  disabled={disabled}
                />
              </label>
            </div>

            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <label className="block">
                <span className="block text-xs font-medium text-text-sekundaer">
                  {t("typeLabel")}
                </span>
                <select
                  value={cf.type}
                  onChange={(e) =>
                    update(idx, { type: e.target.value as CustomFieldType })
                  }
                  className="input mt-1 w-full"
                  disabled={disabled}
                >
                  {(Object.keys(TYPE_LABEL) as CustomFieldType[]).map((tp) => (
                    <option key={tp} value={tp}>
                      {TYPE_LABEL[tp]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="block text-xs font-medium text-text-sekundaer">
                  {t("hintAi")}
                </span>
                <input
                  type="text"
                  value={cf.description}
                  onChange={(e) => update(idx, { description: e.target.value })}
                  placeholder={t("hintAiPlaceholder")}
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
                className="btn btn-still inline-flex items-center gap-1 text-xs"
                style={{ color: "var(--am-fehler)" }}
                disabled={disabled}
              >
                <Trash2 className="h-3 w-3" strokeWidth={1.75} />
                {t("removeBtn")}
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
