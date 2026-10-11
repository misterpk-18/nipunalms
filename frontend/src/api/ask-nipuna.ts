import { get, list, post, type Page } from "./client";
import type { DateTime } from "./types";

export type AssistantState = "AI Available" | "Configuration Pending" | "Quota Limited" | "Disabled";
export type Usage = { used: number; limit: number; resets_at: DateTime };

export type AssistantStatus = {
  status: AssistantState;
  mode: "ai" | "rules" | "off";
  audience: "Student" | "Staff";
  usage: Usage;
  actions: string[];
  scope_note: string;
};

export type AiAnswer = {
  ai_query_id: number;
  question: string;
  action: string | null;
  answer: string;
  /** False when the answer says it had nothing to go on, or the question was refused: the screen then offers a person's help. */
  answered: boolean;
  status: "Answered" | "Refused" | "Failed";
  refusal_reason: string | null;
  is_fallback: boolean;
  model: string;
  sources: { type: string; id?: number; code?: string }[];
  scope_note: string;
  warnings: string[];
  feedback: "Helpful" | "Not helpful" | null;
  created_at: DateTime;
  usage?: Usage;
};

export const askApi = {
  status: () => get<AssistantStatus>("/ask-nipuna/status"),
  ask: (question: string, action?: string) => post<AiAnswer>("/ask-nipuna/queries", { question, action: action ?? null }),
  /** The latest 30 questions, oldest first: the order a chat reads in. */
  history: (page = 1): Promise<Page<AiAnswer>> => list<AiAnswer>("/ask-nipuna/queries", { page, per_page: 30, order: "asc" }),
  feedback: (id: number, rating: "Helpful" | "Not helpful", comment?: string) => post<AiAnswer>(`/ask-nipuna/queries/${id}/feedback`, { rating, comment }),
};
