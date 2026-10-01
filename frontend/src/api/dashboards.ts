/** Dashboards (docs/API.md §4.10–4.11): Student Home, Trainer Today, the trainer / academic reports and the staff summaries. Each screen makes one request. */
import { useQuery } from "@tanstack/react-query";
import { get, put } from "./client";
import type { BranchRef, DateOnly, DateTime, UserRef } from "./types";

/** Every card reports Ready, Empty (nothing to show yet) or Unavailable (its source failed; the rest still render). */
export type Gap = { state: "Empty" | "Unavailable"; message?: string | null };
type Card<T> = ({ state: "Ready"; message?: string | null } & T) | Gap;

type BatchRef = { batch_id: number; batch_code: string; course_code: string };
type EnrolmentRef = {
  enrolment_id: number;
  enrolment_code: string;
  course: { course_id: number; course_code: string; title: string };
  kind: string;
  status: string;
};

// ---------------------------------------------------------------- Student Home

export type HomeNextClass = Card<{
  session_id: number;
  session_code: string;
  title: string;
  session_title: string;
  starts_at: DateTime;
  ends_at: DateTime;
  mode: string;
  room: string | null;
  class_state: string;
  trainer: UserRef;
  batch: BatchRef;
  meet_status: string;
  meet_status_label: string;
  organizer_email: string | null;
  join: { enabled: boolean; reason: string | null; url: string | null };
}>;

export type StudentHome = {
  student: { student_id: number; student_code: string; full_name: string; name_te: string | null; service_branch: BranchRef };
  as_of: DateTime;
  primary_enrolment: EnrolmentRef | null;
  next_class: HomeNextClass;
  due_work: Card<{
    assignments: number;
    required_assignments: number;
    tests: number;
    nearest: { kind: "assignment"; id: number; code: string; title: string; due_at: DateTime; state: string; is_required: boolean } | null;
  }>;
  course_progress: Card<{ enrolment: EnrolmentRef; delivered_sessions: number; planned_sessions: number; percent: number | null }>;
  continue_learning: Card<{
    basis: string;
    track: { track_code: string; track_name: string } | null;
    module: { module_id: number; title: string };
    topic: { topic_id: number; title: string };
  }>;
  latest_recording: Card<{
    recording_id: number;
    title: string;
    class_date: DateTime;
    status: string;
    access_state: string;
    access_until: DateOnly | null;
    playable: boolean;
  }>;
  upcoming_work: Card<{ id: number; code: string; title: string; kind: string; status: string; opens_at: DateTime | null; closes_at: DateTime | null }>;
  attendance_alert: Card<{
    attendance_state: string;
    percent: number | null;
    alert: boolean;
    alert_threshold: number;
    latest_absence: {
      session_title: string;
      starts_at: DateTime;
      can_request_recovery: boolean;
      recovery: { recovery_id: number; recovery_code: string; status: string; method: string } | null;
    } | null;
  }>;
  certificate: Card<{ status: string; enrolment: EnrolmentRef }>;
  career: Card<{ opted_in: boolean; profile_percent: number }>;
  support: Card<{ open_count: number; requests: { request_code: string; subject: string; status: string; owner: string; sla_breached: boolean }[] }>;
  ask_nipuna: Card<{ status: string; mode: string; used: number; limit: number; resets_at: DateTime }>;
  engagement: {
    state: "Fresh" | "Stale" | "Empty" | "Unavailable";
    refreshed_at?: DateTime | null;
    window_days?: number;
    level?: string | null;
    message?: string | null;
  };
};

// ---------------------------------------------------------------- Trainer Today

export type TodaySession = {
  session_id: number;
  session_code: string;
  title: string;
  starts_at: DateTime;
  ends_at: DateTime;
  mode: string;
  room: string | null;
  state: string;
  delivered_at: DateTime | null;
  notes: string | null;
  batch: BatchRef;
  topic: { topic_id: number; title: string } | null;
  meet: { status: string; label: string; link: string | null; organizer_email: string | null };
  attendance: {
    seats: number;
    marked: number;
    not_yet_marked: number;
    present: number;
    absent: number;
    late: number;
    excused: number;
    locked: boolean;
    can_mark: boolean;
  };
  recording: { count: number; mapping: "Mapped" | "Pending Verification" };
};

export type TrainerToday = {
  as_of: DateTime;
  scope_note: string;
  assigned_batches: number;
  tiles: {
    sessions: Card<{ count: number; window_days: number; next_starts_at: DateTime | null }>;
    reviews: Card<{ count: number; oldest_submitted_at: DateTime | null; oldest_age_days: number | null }>;
    support_flags: Card<{ count: number; assigned_students: number }>;
  };
  today: Card<{ date: DateOnly; sessions: TodaySession[] }>;
};

// ---------------------------------------------------------------- Reports

type ReportState = "Calculated" | "Partial Data" | "Empty" | "Not Configured" | "Unavailable";

export type TrainerReports = {
  as_of: DateTime;
  scope_note: string;
  batches: Card<{
    rows: {
      batch: BatchRef;
      batch_state: string;
      students: number;
      delivery: { percent: number | null };
      attendance: { percent: number | null; partial_data: number; state: ReportState };
      alerts: number;
    }[];
  }>;
  review_turnaround: {
    state: ReportState;
    reviewed?: number;
    measured?: number;
    missing_timestamps?: number;
    average_hours?: number | null;
    message?: string | null;
  };
  engagement: { state: "Fresh" | "Stale" | "Unavailable"; refreshed_at?: DateTime | null; window_days?: number; students?: number; message?: string | null };
};

export type AcademicReportBlock = {
  branch: BranchRef;
  curriculum_delivered: { state: ReportState; percent?: number | null; batches?: number; message?: string | null };
  attendance: {
    state: ReportState;
    percent?: number | null;
    partial_data_students?: number;
    alerts?: number;
    recovery?: { requested: number; approved: number; completed: number; rejected: number; approved_or_completed: number };
    message?: string | null;
  };
  completion_reviews: { state: ReportState; closed?: number; open?: number; completed_without_review?: number; message?: string | null };
  certificate_lead_time: { state: ReportState; average_days?: number | null; issued?: number; message?: string | null };
};

export type AcademicReports = { as_of: DateTime; branches: AcademicReportBlock[] };

export const dashboardsApi = {
  home: () => get<StudentHome>("/me/home"),
  trainerToday: () => get<TrainerToday>("/trainer/today"),
  trainerReports: () => get<TrainerReports>("/trainer/reports"),
  academicReports: () => get<AcademicReports>("/academic/reports"),
  saveSessionNotes: (sessionId: number, notes: string) => put<{ session_id: number; notes: string | null }>(`/class-sessions/${sessionId}/notes`, { notes }),
};

export const dashboardKeys = {
  home: ["me", "home"] as const,
  today: ["trainer", "today"] as const,
  trainerReports: ["trainer", "reports"] as const,
  academicReports: ["academic", "reports"] as const,
  academic: ["dashboard", "academic"] as const,
  branch: ["dashboard", "branch"] as const,
  admin: ["dashboard", "admin"] as const,
  founder: ["dashboard", "founder"] as const,
};

export const useMyHome = () => useQuery({ queryKey: dashboardKeys.home, queryFn: dashboardsApi.home });
export const useTrainerToday = () => useQuery({ queryKey: dashboardKeys.today, queryFn: dashboardsApi.trainerToday });
export const useTrainerReports = () => useQuery({ queryKey: dashboardKeys.trainerReports, queryFn: dashboardsApi.trainerReports });
export const useAcademicReports = () => useQuery({ queryKey: dashboardKeys.academicReports, queryFn: dashboardsApi.academicReports });

// ---------------------------------------------------------------- Staff dashboards
/** A CRM-authoritative figure the CRM has not sent: never a number, rendered as "Unavailable". */
export type NotConfigured = { state: "Not Configured"; reason: string; refreshed_at: DateTime | null };
/** A CRM figure from the branches' latest BranchFinanceSnapshot: money as a string, counts as numbers. */
export type CrmValue = {
  state: "Configured" | "Partial Data";
  unit: "INR" | "count";
  value: string | number;
  target: string | number | null;
  period: { label: string; start: DateOnly; end: DateOnly } | null;
  as_of: DateTime;
  stale: boolean;
  missing_branches: BranchRef[];
  detail: Record<string, unknown> | null;
};
export type CrmFigure = NotConfigured | CrmValue;

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
  crm: { verified_collections: CrmFigure; new_paid_admissions: CrmFigure; overdue_followups: CrmFigure };
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
  crm: { overdue_payment_verifications: CrmFigure };
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
  crm: { verified_collections: CrmFigure; new_paid_admissions: CrmFigure; overdue_amount: CrmFigure };
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

export const useAcademicSummary = () => useQuery({ queryKey: dashboardKeys.academic, queryFn: () => get<AcademicSummary>("/academic/summary") });
export const useBranchDashboard = () => useQuery({ queryKey: dashboardKeys.branch, queryFn: () => get<BranchSummary>("/branch/summary") });
export const useAdminSummary = () => useQuery({ queryKey: dashboardKeys.admin, queryFn: () => get<AdminSummary>("/admin/summary") });
export const useFounderSummary = () => useQuery({ queryKey: dashboardKeys.founder, queryFn: () => get<FounderSummary>("/founder/summary") });
