import { apiDelete, apiGet, apiPost, apiPut } from "./client";

export type TemplateDto = {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  is_system: boolean;
  version: number;
  output_schema: Record<string, unknown>;
  is_customized?: boolean;
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
): Promise<void> {
  await apiPut(`/api/v1/templates/${id}/prompt`, { system_prompt: systemPrompt });
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
