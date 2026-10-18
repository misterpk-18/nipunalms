/** The trainer's People and Grade screens (UX plan U13): To grade, students at risk, the Students and Batches lists and their pages. */
import { useQuery } from "@tanstack/react-query";
import { get } from "./client";
import type { ReviewDue } from "./assessments";
import type { DateTime } from "./types";
import type { AssignedStudent, SupportSummary } from "./support";

type BatchRef = { batch_id: number; batch_code: string; course_code: string; display_name?: string | null };
type StudentRef = { student_id: number; student_code: string; full_name: string };

// ---------------------------------------------------------------- To grade

export type GradeItem = {
  key: string;
  /** A hand-in ("submission") or a test attempt ("attempt"). */
  kind: "submission" | "attempt";
  id: number;
  title: string;
  type: string;
  student: StudentRef;
  batch: BatchRef;
  submitted_at: DateTime | null;
  is_late: boolean;
  review_due: ReviewDue | null;
  overdue: boolean;
  /** A review of a hand-in has been started (an attempt has no separate start). */
  started: boolean;
  max_marks: string;
  /** Written or coding answers still to mark (attempts only). */
  to_mark: number | null;
};

export type ToGrade = {
  as_of: DateTime;
  items: GradeItem[];
  counts: { total: number; submissions: number; attempts: number; overdue: number };
  batches: BatchRef[];
};

// ---------------------------------------------------------------- at risk

export type RiskReason = { kind: "attendance" | "work" | "unmarked" | "review_overdue"; label: string; detail: string; to: string; action: string };

export type AtRiskBatch = {
  batch: BatchRef;
  batch_state: string;
  students: number;
  at_risk: number;
  rows: { student: StudentRef; enrolment_id: number; reasons: RiskReason[] }[];
};

export type AtRisk = { as_of: DateTime; date: string; batches: AtRiskBatch[]; totals: { students: number; at_risk: number } };

// ---------------------------------------------------------------- students

export type Measures = {
  attendance_pct: number | null;
  attendance_state: string | null;
  delivery_pct: number | null;
  required_pct: number | null;
  unmarked: number;
  last_activity_at: DateTime | null;
};

export type StudentRow = AssignedStudent & Measures & { reasons: RiskReason[] };

export type SessionLine = {
  session_id: number;
  title: string;
  starts_at: DateTime;
  ends_at: DateTime;
  mode: string;
  room: string | null;
  state: string;
  state_label: string;
  batch: BatchRef;
  topic: { topic_id: number; title: string } | null;
};

export type TrainerBatchRow = {
  batch: {
    batch_id: number;
    batch_code: string;
    display_name: string | null;
    course: { course_id: number; course_code: string; title: string };
    mode: string;
    planned_start: string | null;
    planned_end: string | null;
    state: string;
    state_label: string;
    allocated_count: number;
    capacity: number;
    schedule_days: string[];
    start_time: string | null;
    end_time: string | null;
    location: string | null;
  };
  students: number;
  at_risk: number;
  next_class: SessionLine | null;
  attendance_pct: number | null;
  delivery_pct: number | null;
};

export type BatchPage = {
  batch: TrainerBatchRow["batch"];
  sessions: { coming: SessionLine[]; recent: SessionLine[] };
  roster: (Measures & { student: StudentRef; enrolment: { enrolment_id: number }; open_requests: number; reasons: RiskReason[] })[];
  assignments: {
    assignment_id: number;
    title: string;
    status: "Draft" | "Released" | "Withdrawn";
    due_at: DateTime;
    is_required: boolean;
    counts: { submitted: number; awaiting_review: number; reviewed: number; resubmission_requested: number } | null;
  }[];
  content: { content_item_id: number; item_code: string; title: string; content_type: string; status: string; version_no: number; updated_at: DateTime }[];
  progress: { students: number; delivery_pct: number | null; attendance_pct: number | null; required_pct: number | null; alerts: number; at_risk: number };
};

export type StudentWorkRow = {
  assignment: { assignment_id: number; assignment_code: string; title: string };
  is_required: boolean;
  due_at: DateTime;
  state: "Not submitted" | "Submitted" | "Under Review" | "Reviewed" | "Resubmission Requested";
  overdue: boolean;
  late: boolean;
  submitted_at: DateTime | null;
  marks: string | null;
  max_marks: string;
  submission_id: number | null;
  to_grade: boolean;
};

export type StudentPage = {
  student: StudentRef;
  enrolments: (Measures & {
    enrolment: { enrolment_id: number; enrolment_code: string; course: { title: string; course_code: string }; status: string };
    batch: BatchRef;
    reasons: RiskReason[];
    attendance: { session_id: number; title: string; starts_at: DateTime; status: "Present" | "Absent" | "Late" | "Excused" | null }[];
    assignments: StudentWorkRow[];
    results: { item: { kind: string; title: string; type: string }; status: string; marks: string; max_marks: string }[];
  })[];
  flags: SupportSummary[];
};

export const trainerApi = {
  toGrade: (batchId?: number) => get<ToGrade>("/trainer/to-grade", { batch_id: batchId }),
  atRisk: () => get<AtRisk>("/trainer/at-risk"),
  students: (query: { q?: string; batch_id?: number } = {}) => get<StudentRow[]>("/trainer/students", query),
  batches: () => get<TrainerBatchRow[]>("/trainer/batches"),
  batch: (id: number) => get<BatchPage>(`/trainer/batches/${id}`),
  student: (id: number) => get<StudentPage>(`/trainer/students/${id}`),
};

export const trainerKeys = {
  toGrade: (batchId?: number) => ["trainer", "to-grade", batchId ?? null] as const,
  atRisk: ["trainer", "at-risk"] as const,
  students: (q: string, batchId: number | null) => ["trainer", "students", q, batchId] as const,
  batches: ["trainer", "batches"] as const,
  batch: (id: number) => ["trainer", "batch", id] as const,
  student: (id: number) => ["trainer", "student", id] as const,
};

export const useToGrade = (batchId?: number) => useQuery({ queryKey: trainerKeys.toGrade(batchId), queryFn: () => trainerApi.toGrade(batchId) });
export const useAtRisk = () => useQuery({ queryKey: trainerKeys.atRisk, queryFn: trainerApi.atRisk });
