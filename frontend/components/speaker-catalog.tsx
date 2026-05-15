"use client";

import { Pencil, Plus, Star, Trash2, UserRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import {
  createSpeaker,
  deleteSpeaker,
  fetchSpeakers,
  updateSpeaker,
  type OrgSpeaker,
} from "@/lib/api/speakers";

/**
 * Org-Speaker-Katalog für /einstellungen.
 *
 * Voiceprints werden nicht hier verwaltet — sie wachsen automatisch
 * sobald der User im Transkript-Edit-Modus einen Cluster einem
 * Sprecher zuweist. Hier:
 *   - Sprecher anlegen / umbenennen / Beschreibung pflegen
 *   - is_self toggeln (max. 1 pro Org)
 *   - Voiceprint zurücksetzen (falls falsche Stimme reingelernt wurde)
 *   - Sprecher löschen (cascadiert auf Samples + setzt cluster auf pending)
 */
export function SpeakerCatalog() {
  const toast = useToast();
  const [speakers, setSpeakers] = useState<OrgSpeaker[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    fetchSpeakers().then(setSpeakers).catch(() => setSpeakers([]));
  }, []);

  function refresh() {
    fetchSpeakers().then(setSpeakers).catch(() => {});
  }

  if (speakers === null) {
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
            Sprecher anlegen
          </button>
        )}
      </div>

      {adding && (
        <SpeakerForm
          mode="create"
          onCancel={() => setAdding(false)}
          onSaved={(s) => {
            setAdding(false);
            refresh();
            toast.show({
              message: `Sprecher „${s.display_name}" angelegt.`,
              variant: "success",
            });
          }}
        />
      )}

      {speakers.length === 0 && !adding && (
        <p className="text-sm text-text-secondary">
          Noch keine Sprecher angelegt. Sie können Personen hier anlegen
          (Insilo lernt die Stimme dann beim ersten Zuweisen im
          Transkript), oder den Katalog wachsen lassen indem Sie in einer
          Besprechung „SPEAKER_00" einem neuen Namen zuweisen.
        </p>
      )}

      {speakers.length > 0 && (
        <div className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-white">
          {speakers.map((s) =>
            editingId === s.id ? (
              <div key={s.id} className="p-3">
                <SpeakerForm
                  mode="edit"
                  initial={s}
                  onCancel={() => setEditingId(null)}
                  onSaved={() => {
                    setEditingId(null);
                    refresh();
                  }}
                />
              </div>
            ) : (
              <SpeakerRow
                key={s.id}
                speaker={s}
                onEdit={() => setEditingId(s.id)}
                onAfterDelete={refresh}
              />
            ),
          )}
        </div>
      )}
    </div>
  );
}

function SpeakerRow({
  speaker,
  onEdit,
  onAfterDelete,
}: {
  speaker: OrgSpeaker;
  onEdit: () => void;
  onAfterDelete: () => void;
}) {
  const toast = useToast();

  function handleDelete() {
    if (
      !confirm(
        `Sprecher „${speaker.display_name}" löschen? Alle Voiceprints und Meeting-Zuordnungen werden entfernt.`,
      )
    )
      return;
    deleteSpeaker(speaker.id)
      .then(() => {
        toast.show({ message: "Sprecher gelöscht.", variant: "success" });
        onAfterDelete();
      })
      .catch(() =>
        toast.show({ message: "Löschen fehlgeschlagen.", variant: "error" }),
      );
  }

  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-5 py-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {speaker.is_self ? (
            <Star
              className="h-3.5 w-3.5"
              strokeWidth={2}
              style={{ color: "var(--gold)" }}
              aria-label="Das bin ich"
            />
          ) : (
            <UserRound
              className="h-3.5 w-3.5 text-text-meta"
              strokeWidth={1.75}
            />
          )}
          <span className="font-medium text-text-primary">
            {speaker.display_name}
          </span>
          {speaker.has_voiceprint ? (
            <span className="rounded-full bg-surface-soft px-2 py-0.5 text-xs text-text-secondary">
              {speaker.sample_count}{" "}
              {speaker.sample_count === 1 ? "Stimmprobe" : "Stimmproben"}
            </span>
          ) : (
            <span className="rounded-full bg-surface-soft px-2 py-0.5 text-xs text-text-meta">
              noch keine Stimmprobe
            </span>
          )}
        </div>
        {speaker.description && (
          <p className="mt-1 text-sm text-text-secondary">
            {speaker.description}
          </p>
        )}
        <p className="mt-1 text-xs text-text-meta">
          Angelegt {formatDate(speaker.created_at)}
          {speaker.last_heard_at && (
            <> · zuletzt gehört {formatDate(speaker.last_heard_at)}</>
          )}
        </p>
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onEdit}
          className="rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft hover:text-text-primary"
          aria-label="Bearbeiten"
        >
          <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
        </button>
        <button
          type="button"
          onClick={handleDelete}
          className="rounded-md p-1.5 text-text-meta transition hover:bg-surface-soft"
          aria-label="Löschen"
        >
          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
        </button>
      </div>
    </div>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function SpeakerForm({
  mode,
  initial,
  onSaved,
  onCancel,
}: {
  mode: "create" | "edit";
  initial?: OrgSpeaker;
  onSaved: (s: OrgSpeaker) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.display_name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [isSelf, setIsSelf] = useState(initial?.is_self ?? false);
  const [clearVoiceprint, setClearVoiceprint] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Name darf nicht leer sein.");
      return;
    }
    setSaving(true);
    try {
      const saved =
        mode === "edit" && initial
          ? await updateSpeaker(initial.id, {
              display_name: trimmed,
              description: description.trim(),
              is_self: isSelf,
              clear_voiceprint: clearVoiceprint,
            })
          : await createSpeaker({
              display_name: trimmed,
              description: description.trim(),
              is_self: isSelf,
            });
      onSaved(saved);
    } catch (err: unknown) {
      console.error("save speaker failed", err);
      if (
        typeof err === "object" &&
        err !== null &&
        "status" in err &&
        (err as { status: number }).status === 409
      ) {
        setError("Ein Sprecher mit diesem Namen existiert bereits.");
      } else {
        setError("Speichern fehlgeschlagen.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-md bg-surface-soft p-4">
      <label className="block">
        <span className="block text-xs font-medium text-text-secondary">
          Name
        </span>
        <input
          autoFocus
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="z. B. Kai Böhm"
          maxLength={120}
          className="input mt-1 w-full"
          disabled={saving}
        />
      </label>

      <label className="block">
        <span className="block text-xs font-medium text-text-secondary">
          Beschreibung (optional)
        </span>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="z. B. Mandant Müller GmbH"
          maxLength={500}
          className="input mt-1 w-full"
          disabled={saving}
        />
      </label>

      <label className="inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={isSelf}
          onChange={(e) => setIsSelf(e.target.checked)}
          disabled={saving}
        />
        <span>
          Das bin ich
          <span className="ml-2 text-xs text-text-meta">
            (Zusammenfassungen dürfen mich mit „Sie" ansprechen — max. 1 pro
            Organisation)
          </span>
        </span>
      </label>

      {mode === "edit" && initial?.has_voiceprint && (
        <label className="inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={clearVoiceprint}
            onChange={(e) => setClearVoiceprint(e.target.checked)}
            disabled={saving}
          />
          <span>
            Stimmprobe zurücksetzen
            <span className="ml-2 text-xs text-text-meta">
              (alle {initial.sample_count} Samples werden gelöscht, Insilo lernt
              die Stimme neu beim nächsten Zuweisen)
            </span>
          </span>
        </label>
      )}

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
          {saving
            ? "Speichert …"
            : mode === "edit"
            ? "Speichern"
            : "Anlegen"}
        </button>
      </div>
    </form>
  );
}
