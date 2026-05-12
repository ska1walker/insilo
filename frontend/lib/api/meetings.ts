import { apiDelete, apiGet, apiPost, apiRequest } from "./client";

export type MeetingDto = {
  id: string;
  title: string;
  created_at: string;     // ISO8601
  duration_ms: number;
  mime_type: string;
  byte_size: number;
  status: string;
  audio_url?: string;     // signed playback URL, only on detail
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
}): Promise<MeetingDto> {
  const form = new FormData();
  form.append("audio", args.blob, "recording");
  form.append("title", args.title);
  form.append("duration_ms", String(args.durationMs));
  form.append("mime_type", args.mimeType);
  return apiRequest<MeetingDto>("/api/v1/recordings", {
    method: "POST",
    body: form,
  });
}

export async function deleteMeeting(id: string): Promise<void> {
  await apiDelete<void>(`/api/v1/meetings/${id}`);
}
