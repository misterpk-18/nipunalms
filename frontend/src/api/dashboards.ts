/** Staff dashboard summaries: one read per workspace (API_PLAN §5, P3). */
import { useQuery } from "@tanstack/react-query";
import { get } from "./client";
import type { BranchRef, DateTime } from "./types";

/** A CRM-authoritative figure the LMS does not hold: never a number, rendered as "Unavailable". */
export type NotConfigured = { state: "Not Configured"; reason: string; refreshed_at: DateTime | null };

type Scope = { branches: BranchRef[]; all_branches: boolean; label: string };
export type BatchRisk = {
  batch_id: number;
  batch_code: string;
  branch: BranchRef;
  state: string;
  readiness: string;
  reason: string | null;
  recovery_owner: string | null;
};
type Count = { count: number };

export type AcademicSummary = {
  as_of: DateTime;
  scope: Scope;
  allocation_queue: Count & { curriculum_mapping_pending: number; allocation_pending: number };
  results_awaiting_publication: Count;
  recording_exceptions: Count;
  batches_ready: { ready: number; total: number };
  reviews_awaiting: Count & { content: number; completion: number; certificates: number };
  open_exceptions: Count & { awaiting_owner: number };
  batch_risks: BatchRisk[];
};

export type BranchSummary = {
  as_of: DateTime;
  scope: Scope;
  crm: { verified_collections: NotConfigured; new_paid_admissions: NotConfigured; overdue_followups: NotConfigured };
  batches_running: Count & { total_open: number };
  schedule_and_recording_exceptions: Count & { recording_exceptions: number; reschedule_requests: number };
  requests_open: Count & { escalations: number; extension_requests: number };
  batch_risks: BatchRisk[];
};

type QueueItem = {
  source: string;
  source_id: number;
  reference: string;
  title: string;
  detail: string | null;
  state: string;
  link: string;
  branch: BranchRef | null;
};

export type AdminSummary = {
  as_of: DateTime;
  scope: Scope;
  crm: { overdue_payment_verifications: NotConfigured };
  integration_failures: Count & { codes: string[]; source: string };
  awaiting_owner: Count;
  integrations_verified: { verified: number; total: number };
  provisioning: Count & { items: QueueItem[] };
  open_exceptions: Count & { by_source: Record<string, { count: number; awaiting_owner: number }> };
  sync: {
    flows: { flow: string; last_successful_at: DateTime | null; state: string; detail: string | null }[];
    failed_events: number;
    pending_outbox: number;
    failed_event_items: QueueItem[];
  };
  ai: {
    state: string;
    student_daily_limit: number;
    staff_daily_limit: number;
    monthly_ceiling: { state: "Configuration Pending" } | { state: "Configured"; amount_inr: number };
  };
};

export type FounderSummary = {
  as_of: DateTime;
  scope: Scope;
  crm: { verified_collections: NotConfigured; new_paid_admissions: NotConfigured; overdue_amount: NotConfigured };
  active_enrolments: Count & { by_branch: { branch: BranchRef; count: number }[] };
  batches_at_risk: Count & { items: BatchRisk[] };
  certificates_awaiting_approval: Count & { by_branch: { branch: BranchRef; count: number }[] };
  decisions: {
    ai_ceiling: { state: "Configuration Pending" } | { state: "Configured"; amount_inr: number };
    access_exceptions: Count & {
      state: "Awaiting Approval";
      items: { request_id: number; request_code: string; student_name: string; scope: string; branch_id: number; requested_at: DateTime }[];
    };
  };
};

export const dashboardKeys = {
  academic: ["dashboard", "academic"] as const,
  branch: ["dashboard", "branch"] as const,
  admin: ["dashboard", "admin"] as const,
  founder: ["dashboard", "founder"] as const,
};

export const useAcademicSummary = () => useQuery({ queryKey: dashboardKeys.academic, queryFn: () => get<AcademicSummary>("/academic/summary") });
export const useBranchDashboard = () => useQuery({ queryKey: dashboardKeys.branch, queryFn: () => get<BranchSummary>("/branch/summary") });
export const useAdminSummary = () => useQuery({ queryKey: dashboardKeys.admin, queryFn: () => get<AdminSummary>("/admin/summary") });
export const useFounderSummary = () => useQuery({ queryKey: dashboardKeys.founder, queryFn: () => get<FounderSummary>("/founder/summary") });
