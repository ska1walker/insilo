"use client";

import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import {
  createTag,
  deleteTag,
  listTags,
  TAG_COLORS,
  updateTag,
  type TagDto,
} from "@/lib/api/tags";
import { TagPill } from "./tag-pill";

/**
 * Tag-Verwaltung in der Einstellungen-Page. Vollständiges CRUD über die
 * Org-Tags: anlegen, umbenennen, Farbe ändern, löschen (mit Undo-Toast).
 */
export function TagManager() {
  const toast = useToast();
  const [tags, setTags] = useState<TagDto[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    listTags().then(setTags).catch(() => setTags([]));
  }, []);

  function refresh() {
    listTags().then(setTags).catch(() => {});
  }

  if (tags === null) {
    return (
      <div className="space-y-2">
        <div className="h-12 animate-pulse rounded bg-surface-soft" />
        <div className="h-12 animate-pulse rounded bg-surface-soft" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="btn-secondary inline-flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            Neuer Tag
          </button>
        )}
      </div>

      {adding && (
        <TagForm
          mode="create"
          onCancel={() => setAdding(false)}
          onSaved={(t) => {
            setAdding(false);
            refresh();
            toast.show({
              message: `Tag „${t.name}" angelegt.`,
              variant: "success",
            });
          }}
        />
      )}

      {tags.length === 0 && !adding && (
        <p className="text-sm text-text-secondary">
          Noch keine Tags. Legen Sie über „Neuer Tag" Ihren ersten an —
          z.&nbsp;B. „Mandant Müller" oder „Q2 Strategie".
        </p>
      )}

      {tags.length > 0 && (
        <div className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-white">
          {tags.map((t) =>
            editingId === t.id ? (
              <div key={t.id} className="p-3">
                <TagForm
                  mode="edit"
                  initial={t}
                  onCancel={() => setEditingId(null)}
                  onSaved={() => {
                    setEditingId(null);
                    refresh();
                  }}
                />
              </div>
            ) : (
              <div
                key={t.id}
                className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
              >
                <TagPill name={t.name} color={t.color} />
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setEditingId(t.id)}
                    className="rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
                    aria-label={`„${t.name}" bearbeiten`}
                  >
                    <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      let cancelled = false;
                      toast.show({
                        message: `Tag „${t.name}" wird gelöscht`,
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
                          try {
                            await deleteTag(t.id);
                            refresh();
                          } catch (err) {
                            console.error(err);
                            toast.show({
                              message:
                                "Tag konnte nicht gelöscht werden.",
                              variant: "error",
                            });
                          }
                        },
                      });
                    }}
                    className="rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft"
                    style={{ color: "var(--text-meta)" }}
                    aria-label={`„${t.name}" löschen`}
                  >
                    <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                  </button>
                </div>
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

function TagForm({
  mode,
  initial,
  onSaved,
  onCancel,
}: {
  mode: "create" | "edit";
  initial?: TagDto;
  onSaved: (t: TagDto) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [color, setColor] = useState(initial?.color ?? TAG_COLORS[0].value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Name darf nicht leer sein.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved =
        mode === "edit" && initial
          ? await updateTag(initial.id, { name: trimmed, color })
          : await createTag({ name: trimmed, color });
      onSaved(saved);
    } catch (err: unknown) {
      console.error("save tag failed", err);
      // 409 == name collision
      if (
        typeof err === "object" &&
        err !== null &&
        "status" in err &&
        (err as { status: number }).status === 409
      ) {
        setError("Ein Tag mit diesem Namen existiert bereits.");
      } else {
        setError("Speichern fehlgeschlagen.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-md bg-surface-soft p-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex-1 min-w-[160px]">
          <span className="block text-xs font-medium text-text-secondary">
            Name
          </span>
          <input
            autoFocus
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="z. B. Mandant Müller"
            maxLength={80}
            className="input mt-1 w-full"
            disabled={saving}
          />
        </label>
        <div>
          <span className="block text-xs font-medium text-text-secondary">
            Farbe
          </span>
          <div className="mt-1 flex flex-wrap gap-1">
            {TAG_COLORS.map((c) => (
              <button
                key={c.value}
                type="button"
                onClick={() => setColor(c.value)}
                className="h-7 w-7 rounded-full border transition"
                style={{
                  background: c.value,
                  borderColor:
                    color === c.value ? "var(--text-primary)" : "var(--border-subtle)",
                  boxShadow:
                    color === c.value
                      ? "0 0 0 2px var(--white) inset"
                      : undefined,
                }}
                title={c.label}
                aria-label={`Farbe: ${c.label}`}
              >
                {color === c.value && (
                  <Check
                    className="mx-auto h-3.5 w-3.5"
                    style={{ color: "var(--white)" }}
                    strokeWidth={3}
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <p className="text-sm" style={{ color: "var(--error)" }}>
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 border-t border-border-subtle pt-3">
        <button
          type="button"
          onClick={onCancel}
          className="btn-tertiary inline-flex items-center gap-1"
          disabled={saving}
        >
          <X className="h-3.5 w-3.5" strokeWidth={2} />
          Abbrechen
        </button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Speichert …" : mode === "edit" ? "Speichern" : "Anlegen"}
        </button>
      </div>
    </form>
  );
}
