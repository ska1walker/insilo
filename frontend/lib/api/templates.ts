import { apiGet } from "./client";

export type TemplateDto = {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  is_system: boolean;
  version: number;
  output_schema: Record<string, unknown>;
};

export async function listTemplates(): Promise<TemplateDto[]> {
  return apiGet<TemplateDto[]>("/api/v1/templates");
}
