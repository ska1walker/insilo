"use client";

import { Check, Pencil, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { useToast } from "@/components/toast";
import { renameMeeting } from "@/lib/api/meetings";

/**
 * Inline-editable meeting title for the detail page. Renders as an H1
 * with a small Pencil-icon next to it; clicking the pencil swaps to an
 * input field. Enter saves, Esc cancels.
 */
export function MeetingTitleEdit({
  meetingId,
  initialTitle,
  onChange,
}: {
  meetingId: string;
  initialTitle: string;
  onChange?: (newTitle: string) => void;
}) {
  const toast = useToast();
  const tMeeting = useTranslations("meeting");
  const tCommon = useTranslations("common");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(initialTitle);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraft(initialTitle);
  }, [initialTitle]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  async function commit() {
    const next = draft.trim();
    if (!next) {
      setDraft(initialTitle);
      setEditing(false);
      return;
    }
    if (next === initialTitle) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await renameMeeting(meetingId, next);
      onChange?.(next);
      setEditing(false);
    } catch (err) {
      console.error("rename failed", err);
      toast.show({
        message: tMeeting("renameFailed"),
        variant: "error",
      });
      setDraft(initialTitle);
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    setDraft(initialTitle);
    setEditing(false);
  }

  if (editing) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") cancel();
          }}
          maxLength={255}
          disabled={saving}
          className="input flex-1 min-w-[280px] text-3xl font-medium md:text-4xl"
          aria-label={tMeeting("renameInputAria")}
        />
        <button
          type="button"
          onClick={commit}
          className="rounded-md p-2 text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
          aria-label={tCommon("save")}
          disabled={saving}
        >
          <Check className="h-5 w-5" strokeWidth={1.75} />
        </button>
        <button
          type="button"
          onClick={cancel}
          className="rounded-md p-2 text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
          aria-label={tCommon("cancel")}
          disabled={saving}
        >
          <X className="h-5 w-5" strokeWidth={1.75} />
        </button>
      </div>
    );
  }

  return (
    <div className="group flex flex-wrap items-baseline gap-2">
      <h1 className="text-3xl font-medium md:text-4xl">{initialTitle}</h1>
      <button
        type="button"
        onClick={() => setEditing(true)}
        className="rounded-md p-1.5 text-text-meta opacity-0 transition hover:bg-surface-soft hover:text-text-primary group-hover:opacity-100 focus:opacity-100"
        aria-label={tMeeting("renameAria")}
        title={tMeeting("renameAria")}
      >
        <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
      </button>
    </div>
  );
}
