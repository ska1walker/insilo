"use client";

import { Mic, Pencil, Plus, Star, Trash2, UserRound, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import { VoiceEnrollmentDialog } from "@/components/voice-enrollment-dialog";
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
  const t = useTranslations("speakerCatalog");
  const toast = useToast();
  const [speakers, setSpeakers] = useState<OrgSpeaker[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [enrollingId, setEnrollingId] = useState<string | null>(null);

  useEffect(() => {
    fetchSpeakers().then(setSpeakers).catch(() => setSpeakers([]));
  }, []);

  function refresh() {
    fetchSpeakers().then(setSpeakers).catch(() => {});
  }

  if (speakers === null) {
    return (
      <div className="space-y-2">
        <div className="h-12 animate-pulse rounded bg-flaeche-1" />
        <div className="h-12 animate-pulse rounded bg-flaeche-1" />
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
            className="btn btn-sekundaer inline-flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            {t("addBtn")}
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
              message: t("createdToast", { name: s.display_name }),
              variant: "success",
            });
          }}
        />
      )}

      {speakers.length === 0 && !adding && (
        <p className="text-sm text-text-sekundaer">
          {t("noneYet")}
        </p>
      )}

      {speakers.length > 0 && (
        <div className="divide-y divide-border-subtle rounded-lg border border-trennlinie bg-seite">
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
                onEnroll={() => setEnrollingId(s.id)}
                onAfterDelete={refresh}
              />
            ),
          )}
        </div>
      )}

      {enrollingId !== null && (() => {
        const target = speakers.find((s) => s.id === enrollingId);
        if (!target) return null;
        return (
          <VoiceEnrollmentDialog
            speaker={target}
            onClose={() => setEnrollingId(null)}
            onSuccess={() => {
              refresh();
              toast.show({
                message: t("sampleSavedToast", { name: target.display_name }),
                variant: "success",
              });
            }}
          />
        );
      })()}
    </div>
  );
}

function SpeakerRow({
  speaker,
  onEdit,
  onEnroll,
  onAfterDelete,
}: {
  speaker: OrgSpeaker;
  onEdit: () => void;
  onEnroll: () => void;
  onAfterDelete: () => void;
}) {
  const t = useTranslations("speakerCatalog");
  const toast = useToast();

  function handleDelete() {
    if (!confirm(t("deleteConfirm", { name: speaker.display_name }))) return;
    deleteSpeaker(speaker.id)
      .then(() => {
        toast.show({ message: t("deletedToast"), variant: "success" });
        onAfterDelete();
      })
      .catch(() =>
        toast.show({ message: t("deleteFailToast"), variant: "error" }),
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
              style={{ color: "var(--am-gold-500)" }}
              aria-label={t("isSelfAria")}
            />
          ) : (
            <UserRound
              className="h-3.5 w-3.5 text-text-gedaempft"
              strokeWidth={1.75}
            />
          )}
          <span className="font-medium text-text-primaer">
            {speaker.display_name}
          </span>
          {speaker.has_voiceprint ? (
            <span className="rounded-full bg-flaeche-1 px-2 py-0.5 text-xs text-text-sekundaer">
              {t("samplesPlural", { count: speaker.sample_count })}
            </span>
          ) : (
            <span className="rounded-full bg-flaeche-1 px-2 py-0.5 text-xs text-text-gedaempft">
              {t("noVoiceprintLabel")}
            </span>
          )}
        </div>
        {speaker.description && (
          <p className="mt-1 text-sm text-text-sekundaer">
            {speaker.description}
          </p>
        )}
        <p className="mt-1 text-xs text-text-gedaempft">
          {t("createdAt", { date: formatDate(speaker.created_at) })}
          {speaker.last_heard_at && (
            <> · {t("lastHeardAt", { date: formatDate(speaker.last_heard_at) })}</>
          )}
        </p>
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onEnroll}
          className="btn btn-still inline-flex items-center gap-1"
          title={
            speaker.has_voiceprint
              ? t("addSampleTitleAddon")
              : t("addSampleTitleNew")
          }
        >
          <Mic className="h-3.5 w-3.5" strokeWidth={1.75} />
          {speaker.has_voiceprint ? t("addSampleBtnAddon") : t("addSampleBtnNew")}
        </button>
        <button
          type="button"
          onClick={onEdit}
          className="rounded-md p-1.5 text-text-gedaempft transition hover:bg-flaeche-1 hover:text-text-primaer"
          aria-label={t("editAria")}
        >
          <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
        </button>
        <button
          type="button"
          onClick={handleDelete}
          className="rounded-md p-1.5 text-text-gedaempft transition hover:bg-flaeche-1"
          aria-label={t("deleteAria")}
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
  const t = useTranslations("speakerCatalog.form");
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
      setError(t("errEmptyName"));
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
        setError(t("errDuplicate"));
      } else {
        setError(t("errSave"));
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-md bg-flaeche-1 p-4">
      <label className="block">
        <span className="block text-xs font-medium text-text-sekundaer">
          {t("name")}
        </span>
        <input
          autoFocus
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("namePlaceholder")}
          maxLength={120}
          className="input mt-1 w-full"
          disabled={saving}
        />
      </label>

      <label className="block">
        <span className="block text-xs font-medium text-text-sekundaer">
          {t("descLabel")}
        </span>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("descPlaceholder")}
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
          {t("isSelf")}
          <span className="ml-2 text-xs text-text-gedaempft">
            {t("isSelfHint")}
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
            {t("clearVoiceprint")}
            <span className="ml-2 text-xs text-text-gedaempft">
              {t("clearVoiceprintHint", { count: initial.sample_count })}
            </span>
          </span>
        </label>
      )}

      {error && (
        <p className="text-sm" style={{ color: "var(--am-fehler)" }}>
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 border-t border-trennlinie pt-3">
        <button
          type="button"
          onClick={onCancel}
          className="btn btn-still inline-flex items-center gap-1"
          disabled={saving}
        >
          <X className="h-3.5 w-3.5" strokeWidth={2} />
          {t("cancel")}
        </button>
        <button type="submit" className="btn btn-primaer" disabled={saving}>
          {saving
            ? t("saving")
            : mode === "edit"
            ? t("save")
            : t("create")}
        </button>
      </div>
    </form>
  );
}
