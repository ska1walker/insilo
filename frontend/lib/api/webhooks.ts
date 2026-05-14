import { apiDelete, apiGet, apiPost, apiPut } from "./client";

export const WEBHOOK_EVENTS = [
  "meeting.created",
  "meeting.ready",
  "meeting.failed",
  "meeting.deleted",
  "meeting.updated",
] as const;

export type WebhookEvent = (typeof WEBHOOK_EVENTS)[number];

export const WEBHOOK_EVENT_LABELS: Record<WebhookEvent, string> = {
  "meeting.created": "Besprechung angelegt",
  "meeting.ready": "Zusammenfassung fertig",
  "meeting.failed": "Verarbeitung fehlgeschlagen",
  "meeting.deleted": "Besprechung gelöscht",
  "meeting.updated": "Besprechung geändert",
};

export type WebhookRead = {
  id: string;
  url: string;
  description: string;
  events: WebhookEvent[];
  is_active: boolean;
  has_secret: boolean;
  created_at: string;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_failure_msg: string | null;
};

export type WebhookCreated = WebhookRead & {
  secret: string;
};

export type WebhookCreate = {
  url: string;
  description?: string;
  events: WebhookEvent[];
  is_active?: boolean;
  secret?: string | null;
};

export type WebhookUpdate = {
  url?: string;
  description?: string;
  events?: WebhookEvent[];
  is_active?: boolean;
  secret?: string | null;
};

export type WebhookDelivery = {
  id: string;
  meeting_id: string | null;
  event: string;
  status_code: number | null;
  response_body: string | null;
  error_message: string | null;
  attempt: number;
  created_at: string;
};

export type WebhookTestResult = {
  ok: boolean;
  status_code?: number | null;
  response_body?: string | null;
  error_message?: string | null;
  elapsed_ms?: number | null;
};

export function fetchWebhooks(): Promise<WebhookRead[]> {
  return apiGet<WebhookRead[]>("/api/v1/webhooks");
}

export function createWebhook(payload: WebhookCreate): Promise<WebhookCreated> {
  return apiPost<WebhookCreated>("/api/v1/webhooks", payload);
}

export function updateWebhook(id: string, payload: WebhookUpdate): Promise<WebhookRead> {
  return apiPut<WebhookRead>(`/api/v1/webhooks/${id}`, payload);
}

export function deleteWebhook(id: string): Promise<void> {
  return apiDelete(`/api/v1/webhooks/${id}`);
}

export function testWebhook(id: string): Promise<WebhookTestResult> {
  return apiPost<WebhookTestResult>(`/api/v1/webhooks/${id}/test`);
}

export function fetchDeliveries(id: string, limit = 50): Promise<WebhookDelivery[]> {
  return apiGet<WebhookDelivery[]>(`/api/v1/webhooks/${id}/deliveries?limit=${limit}`);
}
