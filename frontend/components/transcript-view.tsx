"use client";

import { Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ClusterAssignmentPanel } from "@/components/cluster-assignment-panel";
import {
  type Speaker,
  type Transcript,
  type TranscriptSegment,
  updateTranscriptSpeakers,
} from "@/lib/api/meetings";

type Mode = "view" | "edit";

export function TranscriptView({
  meetingId,
  transcript: initial,
}: {
  meetingId: string;
  transcript: Transcript;
}) {
  const [mode, setMode] = useState<Mode>("view");
  const [speakers, setSpeakers] = useState<Speaker[]>(initial.speakers ?? []);
  const [segments, setSegments] = useState<TranscriptSegment[]>(initial.segments);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pickerIdx, setPickerIdx] = useState<number | null>(null);

  // Reset on parent update (e.g. poll refresh).
  useEffect(() => {
    if (mode === "view") {
      setSpeakers(initial.speakers ?? []);
      setSegments(initial.segments);
    }
  }, [initial, mode]);

  const speakerById = useMemo(
    () => new Map(speakers.map((s) => [s.id, s])),
    [speakers],
  );

  const dirty = useMemo(() => {
    const a = JSON.stringify({
      sp: (initial.speakers ?? []).map((s) => [s.id, s.name]),
      seg: initial.segments.map((s) => s.speaker ?? null),
    });
    const b = JSON.stringify({
      sp: speakers.map((s) => [s.id, s.name]),
      seg: segments.map((s) => s.speaker ?? null),
    });
    return a !== b;
  }, [initial, speakers, segments]);

  function addSpeaker(name: string): Speaker {
    const trimmed = name.trim();
    const id = `s${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`;
    const sp: Speaker = { id, name: trimmed };
    setSpeakers((curr) => [...curr, sp]);
    return sp;
  }

  function renameSpeaker(id: string, name: string) {
    setSpeakers((curr) =>
      curr.map((s) => (s.id === id ? { ...s, name: name.trim() } : s)),
    );
  }

  function removeSpeaker(id: string) {
    setSpeakers((curr) => curr.filter((s) => s.id !== id));
    setSegments((curr) =>
      curr.map((seg) => (seg.speaker === id ? { ...seg, speaker: null } : seg)),
    );
  }

  function assignSegment(idx: number, sid: string | null) {
    setSegments((curr) =>
      curr.map((seg, i) => (i === idx ? { ...seg, speaker: sid } : seg)),
    );
    setPickerIdx(null);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const r = await updateTranscriptSpeakers(meetingId, {
        speakers,
        segments: Object.fromEntries(
          segments.map((seg, i) => [String(i), seg.speaker ?? null]),
        ),
      });
      setSpeakers(r.speakers);
      setSegments(r.segments);
      setSavedAt(Date.now());
      setMode("view");
    } catch (err) {
      console.error("save speakers failed", err);
      setError("Speichern fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setSpeakers(initial.speakers ?? []);
    setSegments(initial.segments);
    setMode("view");
    setError(null);
    setPickerIdx(null);
  }

  return (
    <section className="mt-12">
      <div className="mb-6 flex flex-wrap items-baseline justify-between gap-4">
        <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
          Transkript
        </p>
        <div className="flex items-center gap-3">
          {savedAt && mode === "view" && (
            <span className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-success">
              gespeichert
            </span>
          )}
          <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
            {initial.whisper_model} · {initial.language} ·{" "}
            {initial.word_count} Wörter
          </p>
          {mode === "view" ? (
            segments.length > 0 && (
              <button
                type="button"
                onClick={() => setMode("edit")}
                className="btn-tertiary"
              >
                Sprecher zuweisen
              </button>
            )
          ) : (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCancel}
                className="btn-tertiary"
                disabled={saving}
              >
                Abbrechen
              </button>
              <button
                type="button"
                onClick={handleSave}
                className="btn-primary"
                disabled={saving || !dirty}
              >
                {saving ? "Speichert…" : "Speichern"}
              </button>
            </div>
          )}
        </div>
      </div>

      {mode === "edit" && (
        <>
          <ClusterAssignmentPanel
            meetingId={meetingId}
            onChange={() => {
              // Parent (Meeting-Detail-Page) pollt status alle paar Sekunden,
              // sodass die neu zugewiesenen Namen automatisch im Transkript
              // landen. Wir bleiben hier passiv.
            }}
          />
          <SpeakerRoster
            speakers={speakers}
            onAdd={(name) => addSpeaker(name)}
            onRename={renameSpeaker}
            onRemove={removeSpeaker}
          />
        </>
      )}

      {error && (
        <p className="mb-4 text-sm" style={{ color: "var(--error)" }}>
          {error}
        </p>
      )}

      <div className="rounded-lg border border-border-subtle bg-white p-8">
        {segments.length === 0 && (
          <p className="text-sm text-text-meta">
            Keine Sprache erkannt. Die Aufnahme enthielt nur Stille oder
            Hintergrundrauschen.
          </p>
        )}

        {segments.map((seg, i) => {
          const sp = seg.speaker ? speakerById.get(seg.speaker) : undefined;
          const speakerLabel = sp?.name ?? (seg.speaker || null);
          return (
            <div
              key={i}
              className={`grid grid-cols-[100px_1fr] gap-4 py-3 md:grid-cols-[120px_1fr] md:gap-6 ${
                mode === "edit"
                  ? "rounded-md hover:bg-surface-soft -mx-2 px-2 cursor-pointer transition"
                  : ""
              } ${pickerIdx === i ? "bg-surface-soft -mx-2 px-2 rounded-md" : ""}`}
              onClick={() => {
                if (mode === "edit") {
                  setPickerIdx(pickerIdx === i ? null : i);
                }
              }}
            >
              <div>
                <p className="mono text-[0.8125rem] font-medium text-text-meta">
                  [{formatTime(seg.start)}]
                </p>
                {speakerLabel ? (
                  <p
                    className="mono mt-1 text-[0.8125rem] font-medium uppercase tracking-[0.02em]"
                    style={{ color: "var(--gold-deep)" }}
                  >
                    {speakerLabel}
                  </p>
                ) : (
                  mode === "edit" && (
                    <p className="mono mt-1 text-[0.6875rem] uppercase tracking-[0.08em] text-text-disabled">
                      tippen
                    </p>
                  )
                )}
              </div>
              <div className="min-w-0">
                <p className="text-base leading-relaxed text-text-primary">
                  {seg.text}
                </p>
                {mode === "edit" && pickerIdx === i && (
                  <SegmentPicker
                    speakers={speakers}
                    current={seg.speaker ?? null}
                    onPick={(sid) => assignSegment(i, sid)}
                    onCreate={(name) => {
                      const sp = addSpeaker(name);
                      assignSegment(i, sp.id);
                    }}
                    onClose={() => setPickerIdx(null)}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {mode === "edit" && (
        <p className="mt-4 text-xs text-text-meta">
          Tipp: Klicken Sie einen Abschnitt an, um die Sprecherin oder den
          Sprecher zuzuweisen. Vorhandene Einträge können oben umbenannt
          oder gelöscht werden.
        </p>
      )}
    </section>
  );
}

// ─── Speaker-Roster (über dem Transkript, nur im Edit-Modus) ────────────

function SpeakerRoster({
  speakers,
  onAdd,
  onRename,
  onRemove,
}: {
  speakers: Speaker[];
  onAdd: (name: string) => void;
  onRename: (id: string, name: string) => void;
  onRemove: (id: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  function commitAdd() {
    const name = newName.trim();
    if (name.length === 0) {
      setAdding(false);
      setNewName("");
      return;
    }
    onAdd(name);
    setNewName("");
    setAdding(false);
  }

  return (
    <div className="mb-5 rounded-lg border border-border-subtle bg-surface-soft p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <p className="mono text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
          Sprecher · {speakers.length}
        </p>
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="btn-tertiary inline-flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            Sprecher hinzufügen
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {speakers.map((s) =>
          editingId === s.id ? (
            <SpeakerInlineEdit
              key={s.id}
              initial={s.name}
              onCommit={(name) => {
                if (name.trim()) onRename(s.id, name);
                setEditingId(null);
              }}
              onCancel={() => setEditingId(null)}
            />
          ) : (
            <div
              key={s.id}
              className="inline-flex items-center gap-2 rounded-full border border-border-subtle bg-white py-1 pl-3 pr-1"
            >
              <span className="mono text-[0.8125rem] font-medium uppercase tracking-[0.02em]"
                style={{ color: "var(--gold-deep)" }}>
                {s.name}
              </span>
              <button
                type="button"
                onClick={() => setEditingId(s.id)}
                className="rounded-full p-1 text-text-meta hover:bg-surface-soft hover:text-text-primary"
                aria-label={`${s.name} umbenennen`}
              >
                <Pencil className="h-3 w-3" strokeWidth={2} />
              </button>
              <button
                type="button"
                onClick={() => onRemove(s.id)}
                className="rounded-full p-1 text-text-meta hover:bg-surface-soft hover:text-error"
                aria-label={`${s.name} entfernen`}
              >
                <Trash2 className="h-3 w-3" strokeWidth={2} />
              </button>
            </div>
          ),
        )}

        {adding && (
          <div className="inline-flex items-center gap-1 rounded-full border border-border-strong bg-white py-1 pl-3 pr-1">
            <input
              autoFocus
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitAdd();
                if (e.key === "Escape") {
                  setAdding(false);
                  setNewName("");
                }
              }}
              onBlur={commitAdd}
              placeholder="Name"
              className="bg-transparent text-[0.8125rem] font-medium uppercase tracking-[0.02em] outline-none placeholder:text-text-disabled"
              style={{ color: "var(--gold-deep)", width: "120px" }}
            />
            <button
              type="button"
              onMouseDown={(e) => {
                // Prevent input blur before click fires.
                e.preventDefault();
              }}
              onClick={() => {
                setAdding(false);
                setNewName("");
              }}
              className="rounded-full p-1 text-text-meta hover:bg-surface-soft"
              aria-label="Abbrechen"
            >
              <X className="h-3 w-3" strokeWidth={2} />
            </button>
          </div>
        )}

        {speakers.length === 0 && !adding && (
          <p className="text-sm text-text-meta">
            Noch keine Sprecher angelegt. Klicken Sie auf „Sprecher
            hinzufügen" oder direkt auf einen Abschnitt im Transkript.
          </p>
        )}
      </div>
    </div>
  );
}

function SpeakerInlineEdit({
  initial,
  onCommit,
  onCancel,
}: {
  initial: string;
  onCommit: (name: string) => void;
  onCancel: () => void;
}) {
  const [val, setVal] = useState(initial);
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-border-strong bg-white py-1 pl-3 pr-1">
      <input
        autoFocus
        type="text"
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onCommit(val);
          if (e.key === "Escape") onCancel();
        }}
        onBlur={() => onCommit(val)}
        className="bg-transparent text-[0.8125rem] font-medium uppercase tracking-[0.02em] outline-none"
        style={{ color: "var(--gold-deep)", width: "120px" }}
      />
    </div>
  );
}

// ─── Segment-Picker (inline unter einem Segment) ────────────────────────

function SegmentPicker({
  speakers,
  current,
  onPick,
  onCreate,
  onClose,
}: {
  speakers: Speaker[];
  current: string | null;
  onPick: (sid: string | null) => void;
  onCreate: (name: string) => void;
  onClose: () => void;
}) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
  }

  return (
    <div
      className="mt-3 rounded-md border border-border-strong bg-white p-3"
      onClick={handleClick}
    >
      <div className="mb-2 flex items-baseline justify-between">
        <p className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
          Sprecher wählen
        </p>
        <button
          type="button"
          onClick={onClose}
          className="text-text-meta hover:text-text-primary"
          aria-label="Schließen"
        >
          <X className="h-3.5 w-3.5" strokeWidth={2} />
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {speakers.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onPick(s.id)}
            className={`mono inline-flex rounded-full border px-3 py-1 text-[0.8125rem] font-medium uppercase tracking-[0.02em] transition ${
              current === s.id
                ? "border-gold-deep bg-gold-faint"
                : "border-border-subtle bg-white hover:bg-surface-soft"
            }`}
            style={
              current === s.id
                ? {
                    color: "var(--gold-deep)",
                    background: "var(--gold-faint)",
                    borderColor: "var(--gold-deep)",
                  }
                : { color: "var(--gold-deep)" }
            }
          >
            {s.name}
          </button>
        ))}

        {current !== null && (
          <button
            type="button"
            onClick={() => onPick(null)}
            className="inline-flex rounded-full border border-border-subtle bg-white px-3 py-1 text-[0.8125rem] text-text-meta transition hover:bg-surface-soft"
          >
            Zuweisung entfernen
          </button>
        )}

        {!creating ? (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-border-strong bg-white px-3 py-1 text-[0.8125rem] text-text-meta transition hover:bg-surface-soft"
          >
            <Plus className="h-3 w-3" strokeWidth={2} /> Neu
          </button>
        ) : (
          <div className="inline-flex items-center gap-1 rounded-full border border-border-strong bg-white py-1 pl-3 pr-1">
            <input
              autoFocus
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  const name = newName.trim();
                  if (name.length > 0) onCreate(name);
                  setCreating(false);
                  setNewName("");
                }
                if (e.key === "Escape") {
                  setCreating(false);
                  setNewName("");
                }
              }}
              placeholder="Name"
              className="bg-transparent text-[0.8125rem] font-medium uppercase tracking-[0.02em] outline-none placeholder:text-text-disabled"
              style={{ color: "var(--gold-deep)", width: "120px" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function formatTime(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}
