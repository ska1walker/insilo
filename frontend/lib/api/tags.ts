import { apiDelete, apiGet, apiPost, apiPut } from "./client";

export type TagDto = {
  id: string;
  name: string;
  color: string;
};

export type TagPayload = {
  name: string;
  color?: string;
};

export function listTags(): Promise<TagDto[]> {
  return apiGet<TagDto[]>("/api/v1/tags");
}

export function createTag(payload: TagPayload): Promise<TagDto> {
  return apiPost<TagDto>("/api/v1/tags", payload);
}

export function updateTag(id: string, payload: TagPayload): Promise<TagDto> {
  return apiPut<TagDto>(`/api/v1/tags/${id}`, payload);
}

export async function deleteTag(id: string): Promise<void> {
  await apiDelete(`/api/v1/tags/${id}`);
}

export async function addTagToMeeting(
  meetingId: string,
  tagId: string,
): Promise<void> {
  await apiPost(`/api/v1/meetings/${meetingId}/tags`, { tag_id: tagId });
}

export async function removeTagFromMeeting(
  meetingId: string,
  tagId: string,
): Promise<void> {
  await apiDelete(`/api/v1/meetings/${meetingId}/tags/${tagId}`);
}

/** Kuratierte Farbpalette aus dem Designsystem — keine freie Hex-Eingabe. */
export const TAG_COLORS: { value: string; label: string }[] = [
  { value: "#737065", label: "Standard (Meta)" },
  { value: "#0A0A0A", label: "Schwarz" },
  { value: "#9C8147", label: "Gold dunkel" },
  { value: "#C9A961", label: "Gold" },
  { value: "#4A7C59", label: "Grün" },
  { value: "#B8893C", label: "Bernstein" },
  { value: "#A33A2F", label: "Rot" },
  { value: "#4A4842", label: "Anthrazit" },
];
