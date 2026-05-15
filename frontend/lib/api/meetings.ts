import { apiDelete, apiGet, apiPost, apiPut, apiRequest } from "./client";
import type { TagDto } from "./tags";

export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
  /** Either a speaker id (matches Speaker.id) or null/undefined. */
  speaker?: string | null;
};

export type Speaker = {
  id: string;
  name: string;
};

export type Transcript = {
  segments: TranscriptSegment[];
  speakers: Speaker[];
  full_text: string;
  language: string;
  whisper_model: string;
  word_count: number;
};

export type MeetingStatus =
  | "draft"
  | "uploading"
  | "queued"
  | "transcribing"
  | "transcribed"
  | "summarizing"
  | "embedding"
  | "ready"
  | "failed"
  | "archived";

export type Summary = {
  content: Record<string, unknown>;
  llm_model: string;
  generation_time_ms: number;
  created_at: string | null;
  template_id: string;
  template_name: string;
  template_version: number;
};

export type MeetingDto = {
  id: string;
  title: string;
  created_at: string;     // ISO8601
  duration_ms: number;
  mime_type: string;
  byte_size: number;
  status: MeetingStatus;
  audio_url?: string | null;
  error_message?: string | null;
  template_id?: string | null;
  template_name?: string | null;
  transcript?: Transcript | null;
  summary?: Summary | null;
  tags?: TagDto[];
};

export type ListMeetingsParams = {
  tagIds?: string[];
  q?: string;
};

export async function listMeetings(
  params: ListMeetingsParams = {},
): Promise<MeetingDto[]> {
  const search = new URLSearchParams();
  for (const tagId of params.tagIds ?? []) search.append("tag", tagId);
  if (params.q) search.append("q", params.q);
  const qs = search.toString();
  return apiGet<MeetingDto[]>(`/api/v1/meetings${qs ? `?${qs}` : ""}`);
}

export async function getMeeting(id: string): Promise<MeetingDto> {
  return apiGet<MeetingDto>(`/api/v1/meetings/${id}`);
}

export async function createMeeting(args: {
  blob: Blob;
  title: string;
  durationMs: number;
  mimeType: string;
  templateId?: string;
}): Promise<MeetingDto> {
  const form = new FormData();
  form.append("audio", args.blob, "recording");
  form.append("title", args.title);
  form.append("duration_ms", String(args.durationMs));
  form.append("mime_type", args.mimeType);
  if (args.templateId) form.append("template_id", args.templateId);
  return apiRequest<MeetingDto>("/api/v1/recordings", {
    method: "POST",
    body: form,
  });
}

export async function deleteMeeting(id: string): Promise<void> {
  await apiDelete<void>(`/api/v1/meetings/${id}`);
}

export async function retrySummary(id: string): Promise<void> {
  await apiPost<{ status: string }>(`/api/v1/meetings/${id}/retry-summary`);
}

export type SpeakerAssignment = {
  speakers: Speaker[];
  /** Map of segment-index (as string, JSON-friendly) → speaker id or null. */
  segments: Record<string, string | null>;
};

export async function updateTranscriptSpeakers(
  id: string,
  payload: SpeakerAssignment,
): Promise<{
  status: string;
  speakers: Speaker[];
  segments: TranscriptSegment[];
}> {
  return apiPut(`/api/v1/meetings/${id}/transcript/speakers`, payload);
}

export async function renameMeeting(id: string, title: string): Promise<{
  status: string;
  meeting_id: string;
  updated: string[];
}> {
  return apiRequest(`/api/v1/meetings/${id}`, {
    method: "PATCH",
    body: { title },
  });
}

export type DispatchResult = {
  status: string;
  fanout: number;
  reason?: string;
};

export async function dispatchMeeting(
  id: string,
  webhookIds: string[] = [],
): Promise<DispatchResult> {
  return apiPost(`/api/v1/meetings/${id}/dispatch`, { webhook_ids: webhookIds });
}
