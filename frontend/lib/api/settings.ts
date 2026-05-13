import { apiGet, apiPut } from "./client";

export type SettingsRead = {
  llm_base_url: string;
  llm_api_key_set: boolean;
  llm_api_key_hint: string;
  llm_model: string;
  defaults: {
    llm_base_url: string;
    llm_model: string;
  };
};

export type SettingsWrite = {
  llm_base_url: string;
  /** `null` keeps the existing key, `""` clears it, otherwise overwrites. */
  llm_api_key: string | null;
  llm_model: string;
};

export function fetchSettings(): Promise<SettingsRead> {
  return apiGet<SettingsRead>("/api/v1/settings");
}

export function updateSettings(payload: SettingsWrite): Promise<SettingsRead> {
  return apiPut<SettingsRead>("/api/v1/settings", payload);
}
