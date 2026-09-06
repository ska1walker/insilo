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

/** Kuratierte Farbpalette aus dem AImighty-Designsystem — keine freie
 *  Hex-Eingabe. Jede Farbe trägt als Text auf Weiß mindestens 4,5:1; das
 *  reine Gold (#caa960, 2,24:1) fehlt deshalb, Gold heißt hier Gold-800.
 *  Altpalette (Warmgrau, #C9A961, #A33A2F) ersetzt am 06.09.2026; bestehende
 *  Tags behalten ihren gespeicherten Wert. */
export const TAG_COLORS: { value: string; label: string }[] = [
  { value: "#567595", label: "Standard" },      // blau-500
  { value: "#335578", label: "Blau" },          // blau-600
  { value: "#051729", label: "Hanseatenblau" }, // blau-900
  { value: "#8b6c1f", label: "Gold" },          // gold-800
  { value: "#007e46", label: "Grün" },          // erfolg
  { value: "#066bb8", label: "Hinweisblau" },   // hinweis
  { value: "#9f5100", label: "Bernstein" },     // achtung
  { value: "#ad3f38", label: "Rot" },           // fehler
];
