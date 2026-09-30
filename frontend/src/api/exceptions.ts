/** The exception queue: open exceptions from every slice and the recovery steps logged against them (API_PLAN §5, P3). */
import { useQuery } from "@tanstack/react-query";
import { list, get, post, type Page, type Query } from "./client";
import type { BranchRef, DateTime, UserRef } from "./types";

export type ExceptionSource =
  "CURRICULUM_MAPPING" | "ALLOCATION" | "PROVISIONING" | "RECORDING" | "CRM_EVENT" | "SUPPORT" | "RESULTS" | "ACCESS_EXCEPTION" | "INTEGRATION";

export type ExceptionItem = {
  source: ExceptionSource;
  source_id: number;
  reference: string;
  queue: string;
  branch: BranchRef | null;
  title: string;
  detail: string | null;
  owner: UserRef | null;
  owner_label: string | null;
  awaiting_owner: boolean;
  opened_at: DateTime;
  age_days: number;
  state: string;
  link: string;
  step_count: number;
  last_step_at: DateTime | null;
};

export type RecoveryStep = { step_id: number; source: ExceptionSource; source_id: number; reason: string; logged_by: UserRef; logged_at: DateTime };

const path = (item: Pick<ExceptionItem, "source" | "source_id">) => `/exceptions/${item.source}/${item.source_id}/steps`;

export const exceptionsApi = {
  list: (query: Query): Promise<Page<ExceptionItem>> => list<ExceptionItem>("/exceptions", query),
  steps: (item: Pick<ExceptionItem, "source" | "source_id">) => get<RecoveryStep[]>(path(item)),
  logStep: (item: Pick<ExceptionItem, "source" | "source_id">, reason: string) =>
    post<{ step: RecoveryStep; exception: ExceptionItem }>(path(item), { reason }),
};

export const exceptionKeys = {
  all: ["exceptions"] as const,
  list: (query: Query) => ["exceptions", "list", query] as const,
  steps: (item: Pick<ExceptionItem, "source" | "source_id">) => ["exceptions", "steps", item.source, item.source_id] as const,
};

export const useExceptions = (query: Query) => useQuery({ queryKey: exceptionKeys.list(query), queryFn: () => exceptionsApi.list(query) });
export const useRecoverySteps = (item: Pick<ExceptionItem, "source" | "source_id">, enabled: boolean) =>
  useQuery({ queryKey: exceptionKeys.steps(item), queryFn: () => exceptionsApi.steps(item), enabled });
