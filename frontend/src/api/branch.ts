/** The Branch Manager's workspace (UX plan U14): My work, Waiting for a batch, a batch's steps, Create classes and how students pay. */
import { get, list, post, put, type Query } from "./client";
import type { BatchRef, ClassSession } from "./delivery";
import type { BranchRef, DateOnly, DateTime } from "./types";

// ---------------------------------------------------------------- My work

export type WorkRow = {
  key: "waiting" | "decisions" | "results" | "content" | "attendance" | "support" | "class_day";
  /** The row in plain words ("3 students are waiting for a batch"). */
  what: string;
  where: string | null;
  count: number;
  /** When the longest-waiting item began to wait (a deadline for support). */
  oldest_at: DateTime | null;
  to: string;
  search: Record<string, unknown> | null;
  action: string;
};
export type MyWork = { as_of: DateTime; scope: { label: string; all_branches: boolean }; total: number; rows: WorkRow[] };

// ---------------------------------------------------------------- Waiting for a batch

export type WaitingBatch = BatchRef & {
  state: string;
  state_label: string;
  mode: string;
  capacity: number;
  allocated: number;
  seats_left: number;
  planned_start: DateOnly | null;
  schedule_days: string[];
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  trainers: string[];
};
export type WaitingMatch = {
  batch: WaitingBatch;
  result: "Ready to allocate" | "Review needed";
  warnings: string[];
  /** Set when the seat is for one track of a combo enrolment. */
  track: { enrolment_track_id: number; track_code: string; track_name: string } | null;
};
export type WaitingRow = {
  enrolment: { enrolment_id: number; enrolment_code: string; course: { course_id: number; course_code: string; title: string }; kind: string; status: string };
  student: { student_id: number; student_code: string; full_name: string };
  course: { course_id: number; course_code: string; title: string };
  branch: BranchRef;
  mode: string;
  waiting_days: number;
  allocation_due_on: DateOnly | null;
  overdue: boolean;
  matches: WaitingMatch[];
  /** Open batches the allocation review blocks for this student, with why (for example, they already hold a seat). */
  blocked: { batch: BatchRef; reasons: string[] }[];
};
export type BatchWaiting = { batch: WaitingBatch; seats_left: number; students: WaitingRow[] };

// ---------------------------------------------------------------- the batch's steps

export type StepKey = "created" | "trainer" | "ready" | "confirmed" | "students" | "classes";
export type BatchProblem = { key: string; label: string; detail: string; status: "fail" | "pending"; fix: "trainer" | "details" };
export type BatchProgress = {
  batch_id: number;
  state: string;
  steps: { key: StepKey; label: string; done: boolean }[];
  current: StepKey | null;
  next: { key: "assign_trainer" | "finish_setup" | "confirm" | "add_students" | "create_classes"; label: string } | null;
  note: string | null;
  problems: BatchProblem[];
  warnings: { key: string; label: string; detail: string }[];
  can_confirm: boolean;
  counts: { students: number; capacity: number; classes: number; upcoming: number };
};

// ---------------------------------------------------------------- Create classes

export type PlannedClass = {
  starts_at: DateTime;
  ends_at: DateTime;
  title: string;
  topic_id: number | null;
  blocked: string | null;
  warnings: string[];
};
export type SessionPlan = {
  batch: BatchRef;
  trainer: { user_id: number; full_name: string };
  room: string | null;
  mode: string;
  from: DateOnly;
  until: DateOnly;
  classes: PlannedClass[];
  skipped: { date: DateOnly; reason: string }[];
  truncated: boolean;
  blocking: string[];
  warnings: string[];
  created: ClassSession[];
};

export const branchApi = {
  myWork: (branchId: number | null) => get<MyWork>("/branch/my-work", { branch_id: branchId }),
  waiting: (query: Query = {}) => list<WaitingRow>("/branch/waiting", { per_page: 50, ...query }),
  batchWaiting: (batchId: number) => get<BatchWaiting>(`/batches/${batchId}/waiting`),
  progress: (batchId: number) => get<BatchProgress>(`/batches/${batchId}/progress`),
  confirmBatch: (batchId: number, body: { note?: string; override_reason?: string }) => post<unknown>(`/batches/${batchId}/confirm`, body),
  generate: (batchId: number, body: { preview?: boolean; from_date?: string; until?: string; override_reason?: string }) =>
    post<SessionPlan>(`/batches/${batchId}/generate-sessions`, body),
  paymentInstructions: (branchId: number) =>
    get<{ branch_id: number; branch_name: string; payment_instructions: string | null }>(`/branches/${branchId}/payment-instructions`),
  setPaymentInstructions: (branchId: number, text: string | null) => put<unknown>(`/branches/${branchId}/payment-instructions`, { payment_instructions: text }),
};
