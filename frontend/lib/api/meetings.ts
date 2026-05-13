import { apiDelete, apiGet, apiPost, apiRequest } from "./client";

export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
  speaker?: string | null;
};

export type Transcript = {
  segments: TranscriptSegment[];
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
};

export async function listMeetings(): Promise<MeetingDto[]> {
  return apiGet<MeetingDto[]>("/api/v1/meetings");
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
