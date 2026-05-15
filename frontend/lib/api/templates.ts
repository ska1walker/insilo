import { apiDelete, apiGet, apiPost, apiPut } from "./client";

export type TemplateDto = {
  id: string;
  name: string;
  description: string | null;
  /** Original name (system-template default) — present when an override exists. */
  default_name?: string | null;
  default_description?: string | null;
  /** null = no override, non-null = caller has overridden the display label. */
  display_name?: string | null;
  display_description?: string | null;
  category: string | null;
  is_system: boolean;
  version: number;
  output_schema: Record<string, unknown>;
  is_customized?: boolean;
  /** Few-shot example baked into the template (since v0.1.40). Read-only via UI. */
  few_shot_input?: string | null;
  few_shot_output?: Record<string, unknown> | null;
};

export type TemplateDetail = TemplateDto & {
  default_prompt: string;
  custom_prompt: string | null;
  effective_prompt: string;
  custom_updated_at: string | null;
};

export async function listTemplates(): Promise<TemplateDto[]> {
  return apiGet<TemplateDto[]>("/api/v1/templates");
}

export async function getTemplate(id: string): Promise<TemplateDetail> {
  return apiGet<TemplateDetail>(`/api/v1/templates/${id}`);
}

export async function updateTemplatePrompt(
  id: string,
  systemPrompt: string,
  displayName?: string | null,
  displayDescription?: string | null,
): Promise<void> {
  const payload: Record<string, unknown> = { system_prompt: systemPrompt };
  if (displayName !== undefined) payload.display_name = displayName;
  if (displayDescription !== undefined)
    payload.display_description = displayDescription;
  await apiPut(`/api/v1/templates/${id}/prompt`, payload);
}

export async function resetTemplatePrompt(id: string): Promise<void> {
  await apiDelete(`/api/v1/templates/${id}/prompt`);
}

export type TemplatePayload = {
  name: string;
  description: string;
  system_prompt: string;
};

export async function createTemplate(
  payload: TemplatePayload,
): Promise<TemplateDto> {
  return apiPost<TemplateDto>("/api/v1/templates", payload);
}

export async function updateTemplate(
  id: string,
  payload: TemplatePayload,
): Promise<TemplateDto> {
  return apiPut<TemplateDto>(`/api/v1/templates/${id}`, payload);
}

export async function deleteTemplate(id: string): Promise<void> {
  await apiDelete(`/api/v1/templates/${id}`);
}
