"use client";

import { Plus, Tag as TagIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useToast } from "@/components/toast";
import {
  addTagToMeeting,
  createTag,
  listTags,
  removeTagFromMeeting,
  TAG_COLORS,
  type TagDto,
} from "@/lib/api/tags";
import { TagPill } from "./tag-pill";

/**
 * Inline-Picker für Tags eines einzelnen Meetings.
 *
 * - Zeigt aktuell zugewiesene Tags als entfernbare Pills
 * - „Tag hinzufügen" öffnet ein Popover mit Type-ahead + Inline-Anlage
 * - Optimistic UI: Änderungen erscheinen sofort, Backend-Calls hinten dran
 */
export function TagPicker({
  meetingId,
  initialTags,
  onChange,
}: {
  meetingId: string;
  initialTags: TagDto[];
  /** Aufgerufen wenn sich der Tag-Set lokal verändert hat (für Parent-Updates). */
  onChange?: (tags: TagDto[]) => void;
}) {
  const toast = useToast();
  const [tags, setTags] = useState<TagDto[]>(initialTags);
  const [open, setOpen] = useState(false);
  const [allTags, setAllTags] = useState<TagDto[] | null>(null);
  const [filter, setFilter] = useState("");
  const popoverRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => setTags(initialTags), [initialTags]);

  useEffect(() => {
    if (!open) return;
    listTags().then(setAllTags).catch(() => setAllTags([]));
  }, [open]);

  // Klick außerhalb schließt den Popover
  useEffect(() => {
    if (!open) return;
    function onClick(ev: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(ev.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const attachedIds = useMemo(() => new Set(tags.map((t) => t.id)), [tags]);
  const available = useMemo(() => {
    if (!allTags) return [];
    return allTags
      .filter((t) => !attachedIds.has(t.id))
      .filter((t) =>
        filter.trim() === ""
          ? true
          : t.name.toLowerCase().includes(filter.toLowerCase()),
      );
  }, [allTags, attachedIds, filter]);

  function emit(next: TagDto[]) {
    setTags(next);
    onChange?.(next);
  }

  async function attach(tag: TagDto) {
    const next = [...tags, tag].sort((a, b) => a.name.localeCompare(b.name));
    emit(next);
    setFilter("");
    setOpen(false);
    try {
      await addTagToMeeting(meetingId, tag.id);
    } catch (err) {
      console.error("attach tag failed", err);
      emit(tags); // rollback
      toast.show({
        message: `Tag „${tag.name}" konnte nicht hinzugefügt werden.`,
        variant: "error",
      });
    }
  }

  async function detach(tag: TagDto) {
    const prev = tags;
    emit(tags.filter((t) => t.id !== tag.id));
    try {
      await removeTagFromMeeting(meetingId, tag.id);
    } catch (err) {
      console.error("detach tag failed", err);
      emit(prev);
      toast.show({
        message: `Tag „${tag.name}" konnte nicht entfernt werden.`,
        variant: "error",
      });
    }
  }

  async function createAndAttach(name: string) {
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      const created = await createTag({ name: trimmed });
      setAllTags((curr) =>
        curr ? [...curr, created].sort((a, b) => a.name.localeCompare(b.name)) : [created],
      );
      await attach(created);
    } catch (err) {
      console.error("create tag failed", err);
      toast.show({
        message: "Tag konnte nicht angelegt werden.",
        variant: "error",
      });
    }
  }

  return (
    <div className="relative inline-block">
      <div className="flex flex-wrap items-center gap-1.5">
        {tags.map((t) => (
          <TagPill
            key={t.id}
            name={t.name}
            color={t.color}
            onRemove={() => detach(t)}
          />
        ))}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-1 rounded-full border border-dashed border-border-strong px-2.5 py-0.5 text-[0.75rem] font-medium text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
        >
          <TagIcon className="h-3 w-3" strokeWidth={2} />
          {tags.length === 0 ? "Tag hinzufügen" : "Tag"}
        </button>
      </div>

      {open && (
        <div
          ref={popoverRef}
          className="absolute left-0 top-full z-30 mt-2 w-[280px] rounded-lg border border-border-strong bg-white p-3 shadow-lg"
          style={{ boxShadow: "0 8px 24px rgba(10,10,10,0.08)" }}
        >
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                filter.trim() &&
                available.length === 0 &&
                allTags !== null
              ) {
                e.preventDefault();
                createAndAttach(filter);
              }
              if (e.key === "Escape") setOpen(false);
            }}
            placeholder="Tag suchen oder anlegen …"
            autoFocus
            className="input w-full text-sm"
          />

          <div className="mt-3 max-h-[240px] overflow-y-auto">
            {allTags === null && (
              <p className="text-xs text-text-meta">Lädt …</p>
            )}
            {allTags !== null && available.length === 0 && filter.trim() === "" && (
              <p className="text-xs text-text-meta">
                Keine weiteren Tags. Tippen Sie einen Namen zum Anlegen.
              </p>
            )}
            {allTags !== null && available.length === 0 && filter.trim() !== "" && (
              <button
                type="button"
                onClick={() => createAndAttach(filter)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-text-primary hover:bg-surface-soft"
              >
                <Plus className="h-3.5 w-3.5" strokeWidth={2} />
                <span>
                  Neuen Tag anlegen: <strong>„{filter.trim()}"</strong>
                </span>
              </button>
            )}
            {available.length > 0 && (
              <ul className="space-y-0.5">
                {available.map((t) => (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => attach(t)}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-surface-soft"
                    >
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ background: t.color }}
                      />
                      <span className="truncate text-sm text-text-primary">
                        {t.name}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <p className="mt-2 border-t border-border-subtle pt-2 text-[0.6875rem] text-text-meta">
            Farben &amp; Verwaltung in{" "}
            <a href="/einstellungen" className="underline">
              Einstellungen
            </a>
            .
          </p>
        </div>
      )}
    </div>
  );
}

// Re-export for convenience in pages that just want the color palette.
export { TAG_COLORS };
