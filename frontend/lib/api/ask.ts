import { apiPost } from "./client";

export type AskSource = {
  meeting_id: string;
  meeting_title: string;
  meeting_date: string;
  chunk_index: number;
  content: string;
  score: number;
};

export type AskResponse = {
  question: string;
  answer: string;
  sources: AskSource[];
  llm_model: string;
  elapsed_ms: number;
};

export async function ask(question: string, limit = 6): Promise<AskResponse> {
  return apiPost<AskResponse>("/api/v1/ask", { question, limit });
}

export type SearchResponse = {
  query: string;
  hits: AskSource[];
};

export async function search(query: string, limit = 10): Promise<SearchResponse> {
  return apiPost<SearchResponse>("/api/v1/search", { query, limit });
}
