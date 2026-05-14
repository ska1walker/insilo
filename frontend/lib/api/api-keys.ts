import { apiDelete, apiGet, apiPost } from "./client";

export type ApiKeyRead = {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type ApiKeyCreated = ApiKeyRead & {
  token: string;
};

export type ApiKeyCreate = {
  name: string;
  scopes?: string[];
};

export function fetchApiKeys(): Promise<ApiKeyRead[]> {
  return apiGet<ApiKeyRead[]>("/api/v1/api-keys");
}

export function createApiKey(payload: ApiKeyCreate): Promise<ApiKeyCreated> {
  return apiPost<ApiKeyCreated>("/api/v1/api-keys", payload);
}

export function revokeApiKey(id: string): Promise<void> {
  return apiDelete(`/api/v1/api-keys/${id}`);
}
