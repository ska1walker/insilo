"use client";

import { ChevronDown, Plus, Star, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { useToast } from "@/components/toast";
import {
  assignCluster,
  fetchClusters,
  fetchSpeakers,
  type MeetingCluster,
  type OrgSpeaker,
} from "@/lib/api/speakers";

/**
 * Edit-Modus-Panel oberhalb des Transkripts: pro erkanntem Cluster
 * eine Zeile, in der der User den Cluster einem Org-Speaker zuweist
 * oder einen neuen anlegt. Auto-Matches werden vorab grün gefüllt.
 *
 * Beim Zuweisen lernt das Backend den Voiceprint dazu — der Cluster-
 * Centroid landet als Sample am Org-Speaker, der nächste Durchlauf
 * matcht automatisch.
 */
export function ClusterAssignmentPanel({
  meetingId,
  onChange,
}: {
  meetingId: string;
  /** Wird nach jeder erfolgreichen Zuweisung aufgerufen — parent kann
   *  den Transkript-State neu laden, damit die Namen im Volltext
   *  aktualisiert werden. */
  onChange?: () => void;
}) {
  const toast = useToast();
  const t = useTranslations("clusters");
  const [clusters, setClusters] = useState<MeetingCluster[] | null>(null);
  const [speakers, setSpeakers] = useState<OrgSpeaker[]>([]);
  const [pickerOpenIdx, setPickerOpenIdx] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchClusters(meetingId), fetchSpeakers()])
      .then(([cs, sps]) => {
        if (cancelled) return;
        setClusters(cs);
        setSpeakers(sps);
      })
      .catch(() => {
        if (cancelled) return;
        setClusters([]);
      });
    return () => {
      cancelled = true;
    };
  }, [meetingId]);

  function refresh() {
    Promise.all([fetchClusters(meetingId), fetchSpeakers()])
      .then(([cs, sps]) => {
        setClusters(cs);
        setSpeakers(sps);
      })
      .catch(() => {});
  }

  async function handleAssign(
    clusterIdx: number,
    orgSpeakerId: string | null,
    newName?: string,
  ) {
    try {
      await assignCluster(meetingId, clusterIdx, {
        org_speaker_id: orgSpeakerId,
        new_name: newName,
      });
      refresh();
      onChange?.();
      toast.show({
        message:
          orgSpeakerId || newName ? t("assignedToast") : t("unassignedToast"),
        variant: "success",
      });
    } catch (err: unknown) {
      console.error("assign cluster failed", err);
      if (
        typeof err === "object" &&
        err !== null &&
        "status" in err &&
        (err as { status: number }).status === 409
      ) {
        toast.show({
          message: t("duplicateToast"),
          variant: "error",
        });
      } else {
        toast.show({
          message: t("assignFailedToast"),
          variant: "error",
        });
      }
    } finally {
      setPickerOpenIdx(null);
    }
  }

  if (clusters === null) {
    return (
      <div className="mb-5 h-12 animate-pulse rounded-lg bg-surface-soft" />
    );
  }

  if (clusters.length === 0) {
    return (
      <div className="mb-5 rounded-lg border border-border-subtle bg-surface-soft p-4 text-xs text-text-meta">
        {t("emptyPre137")}
      </div>
    );
  }

  return (
    <div className="mb-5 rounded-lg border border-border-subtle bg-surface-soft p-4">
      <p className="mono mb-3 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-text-meta">
        {t("sectionLabel", { count: clusters.length })}
      </p>

      <div className="space-y-2">
        {clusters.map((c) => (
          <ClusterRow
            key={c.cluster_idx}
            cluster={c}
            speakers={speakers}
            pickerOpen={pickerOpenIdx === c.cluster_idx}
            onTogglePicker={() =>
              setPickerOpenIdx(
                pickerOpenIdx === c.cluster_idx ? null : c.cluster_idx,
              )
            }
            onAssign={(spId, newName) =>
              handleAssign(c.cluster_idx, spId, newName)
            }
          />
        ))}
      </div>
    </div>
  );
}

function ClusterRow({
  cluster,
  speakers,
  pickerOpen,
  onTogglePicker,
  onAssign,
}: {
  cluster: MeetingCluster;
  speakers: OrgSpeaker[];
  pickerOpen: boolean;
  onTogglePicker: () => void;
  onAssign: (orgSpeakerId: string | null, newName?: string) => void;
}) {
  const t = useTranslations("clusters");
  const matched = cluster.org_speaker_id !== null;
  const showScore =
    cluster.match_score !== null &&
    cluster.match_score >= 0 &&
    cluster.match_score < 0.99;
  const scorePct = cluster.match_score
    ? Math.round(cluster.match_score * 100)
    : null;

  return (
    <div className="rounded-md bg-white px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="mono text-[0.6875rem] uppercase tracking-[0.08em] text-text-meta">
            Cluster {cluster.cluster_idx.toString().padStart(2, "0")}
          </span>
          {matched ? (
            <>
              {cluster.is_self && (
                <Star
                  className="h-3 w-3"
                  strokeWidth={2}
                  style={{ color: "var(--gold)" }}
                  aria-label={t("isSelfAria")}
                />
              )}
              <span
                className="mono text-[0.8125rem] font-medium uppercase tracking-[0.02em]"
                style={{ color: "var(--gold-deep)" }}
              >
                {cluster.display_name}
              </span>
              {cluster.assignment === "auto" && showScore && (
                <span
                  className="rounded-full bg-surface-soft px-2 py-0.5 text-[0.6875rem] uppercase tracking-[0.04em] text-text-meta"
                  title={t("scoreTooltip")}
                >
                  {scorePct}%
                </span>
              )}
              <span
                className="rounded-full px-2 py-0.5 text-[0.6875rem] uppercase tracking-[0.04em]"
                style={
                  cluster.assignment === "auto"
                    ? { background: "rgba(74,124,89,0.08)", color: "var(--success)" }
                    : { background: "var(--surface-soft)", color: "var(--text-meta)" }
                }
              >
                {cluster.assignment === "auto" ? t("automatic") : t("manual")}
              </span>
            </>
          ) : (
            <span className="mono text-[0.8125rem] font-medium uppercase tracking-[0.02em] text-text-meta">
              SPEAKER_{cluster.cluster_idx.toString().padStart(2, "0")}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={onTogglePicker}
          className="btn-tertiary inline-flex items-center gap-1"
        >
          {matched ? t("change") : t("assign")}
          <ChevronDown className="h-3 w-3" strokeWidth={2} />
        </button>
      </div>

      {pickerOpen && (
        <ClusterPicker
          speakers={speakers}
          currentId={cluster.org_speaker_id}
          onPick={(id) => onAssign(id)}
          onCreate={(name) => onAssign(null, name)}
          onClear={() => onAssign(null)}
        />
      )}
    </div>
  );
}

function ClusterPicker({
  speakers,
  currentId,
  onPick,
  onCreate,
  onClear,
}: {
  speakers: OrgSpeaker[];
  currentId: string | null;
  onPick: (id: string) => void;
  onCreate: (name: string) => void;
  onClear: () => void;
}) {
  const t = useTranslations("clusters");
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (creating) inputRef.current?.focus();
  }, [creating]);

  function commitCreate() {
    const name = newName.trim();
    if (name) onCreate(name);
    setCreating(false);
    setNewName("");
  }

  // is_self ganz oben, Rest alphabetisch.
  const sorted = [...speakers].sort((a, b) => {
    if (a.is_self !== b.is_self) return a.is_self ? -1 : 1;
    return a.display_name.localeCompare(b.display_name, "de");
  });

  return (
    <div className="mt-3 border-t border-border-subtle pt-3">
      <div className="mb-2 flex flex-wrap gap-2">
        {sorted.map((s) => {
          const active = currentId === s.id;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => onPick(s.id)}
              className="mono inline-flex items-center gap-1 rounded-full border px-3 py-1 text-[0.8125rem] font-medium uppercase tracking-[0.02em] transition"
              style={
                active
                  ? {
                      color: "var(--gold-deep)",
                      background: "var(--gold-faint)",
                      borderColor: "var(--gold-deep)",
                    }
                  : {
                      color: "var(--gold-deep)",
                      borderColor: "var(--border-subtle)",
                      background: "var(--white)",
                    }
              }
              title={
                s.has_voiceprint
                  ? t("samplesTooltip", { count: s.sample_count })
                  : t("noSampleTooltip")
              }
            >
              {s.is_self ? (
                <Star
                  className="h-3 w-3"
                  strokeWidth={2}
                  style={{ color: "var(--gold)" }}
                />
              ) : (
                <UserRound className="h-3 w-3" strokeWidth={1.75} />
              )}
              {s.display_name}
            </button>
          );
        })}

        {!creating ? (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-border-strong bg-white px-3 py-1 text-[0.8125rem] text-text-meta transition hover:bg-surface-soft"
          >
            <Plus className="h-3 w-3" strokeWidth={2} />
            {t("newSpeaker")}
          </button>
        ) : (
          <div className="inline-flex items-center gap-1 rounded-full border border-border-strong bg-white py-1 pl-3 pr-1">
            <input
              ref={inputRef}
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitCreate();
                if (e.key === "Escape") {
                  setCreating(false);
                  setNewName("");
                }
              }}
              placeholder={t("namePlaceholder")}
              maxLength={120}
              className="bg-transparent text-[0.8125rem] font-medium uppercase tracking-[0.02em] outline-none placeholder:text-text-disabled"
              style={{ color: "var(--gold-deep)", width: "120px" }}
            />
          </div>
        )}

        {currentId !== null && (
          <button
            type="button"
            onClick={onClear}
            className="rounded-full border border-border-subtle bg-white px-3 py-1 text-[0.8125rem] text-text-meta transition hover:bg-surface-soft"
          >
            {t("unassign")}
          </button>
        )}
      </div>
    </div>
  );
}
