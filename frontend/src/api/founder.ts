/** The Founder's inbox and its decisions (UX phase U16; docs/API.md §4.20). Each item carries the record as its own screen shows it. */
import { useQuery } from "@tanstack/react-query";
import { get, post, put } from "./client";
import type { Correction } from "./attendance";
import type { CertificateRequest, FinancialException } from "./certificates";
import type { StaffExtensionRequest } from "./content";
import type { CurriculumVersion, RescheduleRequest } from "./delivery";
import type { DateOnly, DateTime, UserRef } from "./types";

export type InboxGroup = "curriculum" | "certificates" | "access" | "other";
export type InboxKind = "curriculum" | "certificate" | "fee_exception" | "access_extension" | "ai_budget" | "bm_reschedule" | "bm_correction";

export type CurriculumDetail = {
  curriculum_version_id: number;
  version_label: string;
  status: "Under Review" | "Approved";
  course: { course_id: number; course_code: string; title: string };
  component: { track_code: string; track_name: string } | null;
  submitted_by: UserRef | null;
  submitted_at: DateTime | null;
  approved_at: DateTime | null;
};
export type AiBudgetDetail = { state: "Configuration Pending" } | { state: "Configured"; amount_inr: number };

type Base<K extends InboxKind, D> = {
  key: string;
  kind: K;
  id: number | string;
  /** What it is, in plain words ("Approve curriculum CV 5.2 for Java"). */
  title: string;
  where: string | null;
  /** When it started waiting; null for the AI budget. */
  since: DateTime | null;
  /** The button on the list ("Review"). */
  action: string;
  /** The Founder page that lists this kind. */
  to: string;
  from_branch_manager: boolean;
  detail: D;
};

export type InboxItem =
  | Base<"curriculum", CurriculumDetail>
  | Base<"certificate", CertificateRequest>
  | Base<"fee_exception", FinancialException>
  | Base<"access_extension", StaffExtensionRequest>
  | Base<"ai_budget", AiBudgetDetail>
  | Base<"bm_reschedule", RescheduleRequest & { can_decide: boolean }>
  | Base<"bm_correction", Correction & { can_decide: boolean }>;

export type FounderInbox = {
  as_of: DateTime;
  total: number;
  counts: Record<InboxKind, number>;
  items: InboxItem[];
  /** Approved versions that will be activated on the day chosen with the approval. */
  scheduled: {
    curriculum_version_id: number;
    version_label: string;
    activate_on: DateOnly;
    course: { course_id: number; course_code: string; title: string };
  }[];
  /** False until the CRM has sent finance figures; the CRM tiles stay hidden until then. */
  crm_connected: boolean;
};

export type CurriculumImpact = {
  curriculum_version_id: number;
  version_label: string;
  status: string;
  activate_on: DateOnly | null;
  course: { course_id: number; course_code: string; title: string };
  previous: { curriculum_version_id: number; version_label: string } | null;
  submitted_by: { user_id: number; full_name: string } | null;
  submitted_at: DateTime | null;
  what_changes: string[];
  who_is_affected: string[];
  added_topics: string[];
  removed_topics: string[];
  batches_getting_it: number;
  batches_staying: number;
  outline: { module: string; topics: string[] }[];
  total_minutes: number;
};

export const founderApi = {
  inbox: (group?: InboxGroup) => get<FounderInbox>("/founder/inbox", { group }),
  impact: (versionId: number) => get<CurriculumImpact>(`/curriculum-versions/${versionId}/impact`),
  /** `activate_on` = today approves and activates in one step; a later day schedules the activation; leave out to approve only. */
  approveCurriculum: (versionId: number, activateOn?: DateOnly) =>
    post<CurriculumVersion & { released: { enrolments_released: number; batches_mapped: number } | null }>(
      `/curriculum-versions/${versionId}/approve`,
      activateOn ? { activate_on: activateOn } : {},
    ),
  activateCurriculum: (versionId: number) => post<CurriculumVersion>(`/curriculum-versions/${versionId}/activate`, {}),
  returnCurriculum: (versionId: number, reason: string) => post<CurriculumVersion>(`/curriculum-versions/${versionId}/return`, { reason }),
  approveAiBudget: (amountInr: number) => put<AiBudgetDetail>("/founder/ai-budget", { amount_inr: amountInr }),
};

export const founderKeys = { inbox: (group?: InboxGroup) => ["founder", "inbox", group ?? "all"] as const };

/** The Founder's inbox, or one page of it; refreshed every minute with the nav badges. */
export const useFounderInbox = (group?: InboxGroup) =>
  useQuery({ queryKey: founderKeys.inbox(group), queryFn: () => founderApi.inbox(group), refetchInterval: 60_000 });
