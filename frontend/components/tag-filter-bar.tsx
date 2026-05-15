"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { listTags, type TagDto } from "@/lib/api/tags";
import { TagPill } from "./tag-pill";

/**
 * Toggleable Tag-Chips zum Filtern der Besprechungs-Liste.
 *
 * Aktive Chips sind voll eingefärbt, inaktive ausgegraut. Klick toggelt.
 * Eltern-Komponente kontrolliert den `selectedIds`-State und reagiert
 * auf `onChange` mit einem neuen `listMeetings({ tagIds })`-Call.
 */
export function TagFilterBar({
  selectedIds,
  onChange,
}: {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}) {
  const t = useTranslations("tags");
  const [tags, setTags] = useState<TagDto[] | null>(null);

  useEffect(() => {
    listTags()
      .then(setTags)
      .catch(() => setTags([]));
  }, []);

  function toggle(id: string) {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  }

  if (tags === null) {
    return (
      <div className="mb-6 h-[34px] animate-pulse rounded-full bg-surface-soft" />
    );
  }

  if (tags.length === 0) {
    return null;
  }

  const anyActive = selectedIds.length > 0;

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <span className="mono mr-1 text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
        {t("filterPrefix")}
      </span>
      {tags.map((t) => (
        <TagPill
          key={t.id}
          name={t.name}
          color={t.color}
          active={selectedIds.includes(t.id)}
          onClick={() => toggle(t.id)}
        />
      ))}
      {anyActive && (
        <button
          type="button"
          onClick={() => onChange([])}
          className="ml-1 inline-flex items-center gap-1 text-[0.75rem] text-text-meta transition hover:text-text-primary"
        >
          <X className="h-3 w-3" strokeWidth={2} />
          {t("resetAll")}
        </button>
      )}
    </div>
  );
}
