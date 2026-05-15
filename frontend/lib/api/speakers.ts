import { apiDelete, apiGet, apiPost, apiPut } from "./client";

export type OrgSpeaker = {
  id: string;
  display_name: string;
  description: string;
  is_self: boolean;
  has_voiceprint: boolean;
  sample_count: number;
  last_heard_at: string | null;
  created_at: string;
};

export type SpeakerCreate = {
  display_name: string;
  description?: string;
  is_self?: boolean;
};

export type SpeakerUpdate = {
  display_name?: string;
  description?: string;
  is_self?: boolean;
  /** Wipe voiceprint + sample history (speaker stays in catalog, no longer auto-matched). */
  clear_voiceprint?: boolean;
};

export type MeetingCluster = {
  cluster_idx: number;
  org_speaker_id: string | null;
  display_name: string | null;
  match_score: number | null;
  assignment: "auto" | "manual" | "pending";
  is_self: boolean;
};

export type ClusterAssign = {
  /** Existing speaker to bind. Set to null to clear. */
  org_speaker_id?: string | null;
  /** Shortcut: create a new org-speaker with this name and bind. */
  new_name?: string;
};

export function fetchSpeakers(): Promise<OrgSpeaker[]> {
  return apiGet<OrgSpeaker[]>("/api/v1/speakers");
}

export function createSpeaker(payload: SpeakerCreate): Promise<OrgSpeaker> {
  return apiPost<OrgSpeaker>("/api/v1/speakers", payload);
}

export function updateSpeaker(id: string, payload: SpeakerUpdate): Promise<OrgSpeaker> {
  return apiPut<OrgSpeaker>(`/api/v1/speakers/${id}`, payload);
}

export function deleteSpeaker(id: string): Promise<void> {
  return apiDelete(`/api/v1/speakers/${id}`);
}

export function fetchClusters(meetingId: string): Promise<MeetingCluster[]> {
  return apiGet<MeetingCluster[]>(`/api/v1/meetings/${meetingId}/clusters`);
}

export function assignCluster(
  meetingId: string,
  clusterIdx: number,
  payload: ClusterAssign,
): Promise<{
  status: string;
  cluster_idx: number;
  org_speaker_id: string | null;
  display_name: string | null;
}> {
  return apiPost(
    `/api/v1/meetings/${meetingId}/clusters/${clusterIdx}/assign`,
    payload,
  );
}

export function reDiarizeMeeting(meetingId: string): Promise<{ status: string }> {
  return apiPost(`/api/v1/meetings/${meetingId}/re-diarize`);
}

export type EnrollResult = {
  status: string;
  voiced_seconds: number;
  total_seconds: number;
  sample_count: number;
  speaker_id: string;
  display_name: string;
};

export async function enrollSpeaker(
  speakerId: string,
  audio: Blob,
  mimeType: string,
): Promise<EnrollResult> {
  const form = new FormData();
  form.append("audio", audio, "enrollment.bin");
  form.append("min_voiced_seconds", "5.0");

  // We use apiPost via FormData so the X-Bfl-User header is included.
  return (await import("./client")).apiPost<EnrollResult>(
    `/api/v1/speakers/${speakerId}/enroll`,
    form,
  );
}
