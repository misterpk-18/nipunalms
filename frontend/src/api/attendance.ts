/** Attendance, recovery, corrections and the four progress measures (docs/API.md §4.7). */
import { useQuery } from "@tanstack/react-query";
import { get, list, post, put, type Page, type Query } from "./client";
import type { DateOnly, DateTime, UserRef } from "./types";

export const ATTENDANCE_STATUSES = ["Present", "Absent", "Late", "Excused"] as const;
export type AttendanceStatus = (typeof ATTENDANCE_STATUSES)[number];
export const RECOVERY_METHODS = ["Recording watched", "Extra session", "Assignment"] as const;

type BatchRef = { batch_id: number; batch_code: string; course_code: string };
type EnrolmentRef = {
  enrolment_id: number;
  enrolment_code: string;
  course: { course_id: number; course_code: string; title: string };
  kind: string;
  status: string;
};
type StudentRef = { student_id: number; student_code: string; full_name: string };
export type SessionRef = { session_id: number; session_code: string; title: string; starts_at: DateTime; ends_at: DateTime; batch: BatchRef };

export type RecoveryRef = { recovery_id: number; recovery_code: string; status: "Requested" | "Approved" | "Rejected" | "Completed"; method: string };

/** A student's own recovery request on an attendance row: its status, what the decider said, and who decides. */
export type RecoveryStatus = RecoveryRef & { decision_note: string | null; target_date: DateOnly | null; decided_at: DateTime | null; decides: string };

/** The latest "report a mistake" request for a class. */
export type CorrectionStatus = {
  correction_id: number;
  status: "Pending" | "Approved" | "Rejected";
  requested_status: AttendanceStatus;
  reason: string;
  requested_at: DateTime;
  decided_at: DateTime | null;
  decision_note: string | null;
  decides: string;
};

/** One thing to do next (My Progress). The screen words each kind and knows where it leads; `params` fill the sentence. */
export type NextStep = {
  kind:
    | "work_overdue"
    | "work_todo"
    | "recovery"
    | "attendance_low"
    | "access_ended"
    | "access_ending"
    | "certificate_fee"
    | "certificate_ready"
    | "topics_left"
    | "inactive";
  course: { course_code: string; title: string } | null;
  params: Record<string, string | number | boolean | null>;
};

export type RegisterSession = {
  session_id: number;
  session_code: string;
  title: string;
  starts_at: DateTime;
  ends_at: DateTime;
  mode: string;
  state: string;
  batch: BatchRef;
  trainer: UserRef;
  seats: number;
  marked: number;
  attendance_state: "Not yet marked" | "Partially marked" | "Marked" | "No seats";
  locked: boolean;
  can_mark: boolean;
};

export type RegisterRow = {
  enrolment: EnrolmentRef;
  student: StudentRef;
  attendance: { attendance_id: number; status: AttendanceStatus; remarks: string | null; marked_by: UserRef; marked_at: DateTime } | null;
  label: string;
  recovery: RecoveryRef | null;
  correction_pending: boolean;
  /** When the student said "I attended" (online classes). The trainer's mark is still the record. */
  student_confirmed_at: DateTime | null;
};

export type Register = {
  session: RegisterSession;
  locked: boolean;
  lock_days: number;
  can_mark: boolean;
  summary: {
    seats: number;
    marked: number;
    not_yet_marked: number;
    confirmed_by_student: number;
    present: number;
    absent: number;
    late: number;
    excused: number;
  };
  rows: RegisterRow[];
};

export type AttendanceMeasure = {
  state: "Not started" | "Partial Data" | "Calculated";
  percent: number | null;
  provisional: boolean;
  delivered_since_joining: number;
  marked: number;
  unmarked: number;
  present: number;
  late: number;
  absent: number;
  excused: number;
  recovered: number;
  alert_threshold: number;
  alert: boolean;
};

export type Measures = {
  delivery: { delivered_sessions: number; planned_sessions: number; percent: number | null };
  attendance: AttendanceMeasure;
  required_learning: { required_topics: number; covered_topics: number; percent: number | null };
  engagement: { level: "High" | "Medium" | "Low" | "Not started"; events_in_window: number; window_days: number; last_activity_at: DateTime | null };
};

export type ProgressBlock = Measures & {
  enrolment: EnrolmentRef;
  joining_date: DateOnly | null;
  batch: BatchRef | null;
  certificate_status: string;
  as_of: DateTime;
};

export type ProgressRow = ProgressBlock & { student: StudentRef };

export type StudentAttendanceRow = {
  session: {
    session_id: number;
    session_code: string;
    title: string;
    starts_at: DateTime;
    ends_at: DateTime;
    mode: string;
    state: string;
    trainer: UserRef;
    batch: BatchRef;
  };
  attendance_id: number | null;
  status: AttendanceStatus | null;
  label: string;
  remarks: string | null;
  marked_at: DateTime | null;
  locked: boolean;
  recovery: RecoveryStatus | null;
  correction: CorrectionStatus | null;
  correction_pending: boolean;
  can_request_recovery: boolean;
};

export type StudentAttendance = { enrolment: EnrolmentRef; joining_date: DateOnly | null; summary: AttendanceMeasure; rows: StudentAttendanceRow[] };

export type Recovery = RecoveryRef & {
  attendance_id: number;
  session: SessionRef;
  enrolment: EnrolmentRef;
  student: StudentRef;
  reason: string;
  requested_by: UserRef;
  requested_at: DateTime;
  decided_at: DateTime | null;
  decision_note: string | null;
  target_date: DateOnly | null;
  completed_at: DateTime | null;
  evidence_note: string | null;
};

export type Correction = {
  correction_id: number;
  session: SessionRef;
  enrolment: EnrolmentRef;
  student: StudentRef;
  previous_status: AttendanceStatus | null;
  requested_status: AttendanceStatus;
  reason: string;
  status: "Pending" | "Approved" | "Rejected";
  requested_by: UserRef;
  requested_at: DateTime;
  decided_at: DateTime | null;
  decision_note: string | null;
};

export type BranchSummary = {
  batches: {
    batch: BatchRef;
    branch: { branch_id: number; branch_code: string; branch_name: string };
    state: string;
    students: number;
    avg_delivery: number | null;
    avg_attendance: number | null;
    avg_required_learning: number | null;
    attendance_alerts: number;
    partial_data: number;
  }[];
  enrolments_by_status: Record<string, number>;
  certificates_by_status: Record<string, number>;
  as_of: DateTime;
};

/** The counts on the tabs of the Branch Manager's Attendance & progress. */
export type AttendanceTabCounts = { students_at_risk: number; recoveries: number; corrections: number };

/** A correction in the Branch Manager's queue: `can_decide` is false when the viewer requested it or marked the entry, or only the Founder or a Super Admin may decide it. */
export type CorrectionRow = Correction & { can_decide?: boolean };

export type MarkBody = {
  default_status?: AttendanceStatus;
  from_confirmations?: boolean;
  entries?: { enrolment_id: number; status: AttendanceStatus; remarks?: string | null }[];
};

export const attendanceApi = {
  sessions: (query: Query) => list<RegisterSession>("/attendance/sessions", query),
  register: (sessionId: number) => get<Register>(`/attendance/sessions/${sessionId}`),
  mark: (sessionId: number, body: MarkBody) => put<Register>(`/attendance/sessions/${sessionId}`, body),
  mine: () => get<StudentAttendance[]>("/me/attendance"),
  confirmAttended: (sessionId: number) => post<{ session_id: number; claimed_at: DateTime }>(`/me/class-sessions/${sessionId}/attendance-confirmation`),
  recoveries: (query: Query) => list<Recovery>("/attendance/recoveries", query),
  requestRecovery: (body: { attendance_id: number; method: string; reason: string }) => post<Recovery>("/attendance/recoveries", body),
  decideRecovery: (id: number, body: { decision: "Approved" | "Rejected"; decision_note?: string; target_date?: string }) =>
    post<Recovery>(`/attendance/recoveries/${id}/decision`, body),
  completeRecovery: (id: number, evidence_note: string) => post<Recovery>(`/attendance/recoveries/${id}/completion`, { evidence_note }),
  corrections: (query: Query) => list<Correction>("/attendance/corrections", query),
  requestCorrection: (body: { session_id: number; enrolment_id: number; requested_status: AttendanceStatus; reason: string }) =>
    post<Correction>("/attendance/corrections", body),
  decideCorrection: (id: number, body: { decision: "Approved" | "Rejected"; decision_note?: string }) =>
    post<Correction>(`/attendance/corrections/${id}/decision`, body),
  myProgress: () => get<ProgressBlock[]>("/me/progress"),
  nextSteps: () => get<NextStep[]>("/me/progress/next-steps"),
  progress: (query: Query) => list<ProgressRow>("/progress/students", query),
  summary: (query: Query) => get<BranchSummary>("/progress/summary", query),
  enrolmentProgress: (enrolmentId: number) => get<ProgressBlock>(`/progress/enrolments/${enrolmentId}`),
  tabCounts: (branchId: number | null) => get<AttendanceTabCounts>("/branch/attendance-summary", { branch_id: branchId }),
  branchCorrections: (query: Query) => list<CorrectionRow>("/attendance/corrections", query),
};

export const attendanceKeys = {
  all: ["attendance"] as const,
  sessions: (query: Query) => ["attendance", "sessions", query] as const,
  register: (sessionId: number) => ["attendance", "register", sessionId] as const,
  mine: ["attendance", "mine"] as const,
  recoveries: (query: Query) => ["attendance", "recoveries", query] as const,
  corrections: (query: Query) => ["attendance", "corrections", query] as const,
  myProgress: ["progress", "mine"] as const,
  nextSteps: ["progress", "next-steps"] as const,
  progress: (query: Query) => ["progress", "students", query] as const,
  summary: (query: Query) => ["progress", "summary", query] as const,
};

export const useRegisterSessions = (query: Query) => useQuery({ queryKey: attendanceKeys.sessions(query), queryFn: () => attendanceApi.sessions(query) });
export const useRegister = (sessionId: number | null) =>
  useQuery({ queryKey: attendanceKeys.register(sessionId ?? 0), queryFn: () => attendanceApi.register(sessionId!), enabled: sessionId !== null });
export const useMyAttendance = () => useQuery({ queryKey: attendanceKeys.mine, queryFn: attendanceApi.mine });
export const useRecoveries = (query: Query) => useQuery({ queryKey: attendanceKeys.recoveries(query), queryFn: () => attendanceApi.recoveries(query) });
export const useCorrections = (query: Query) => useQuery({ queryKey: attendanceKeys.corrections(query), queryFn: () => attendanceApi.corrections(query) });
export const useNextSteps = () => useQuery({ queryKey: attendanceKeys.nextSteps, queryFn: attendanceApi.nextSteps });
export const useMyProgress = () => useQuery({ queryKey: attendanceKeys.myProgress, queryFn: attendanceApi.myProgress });
export const useProgressRows = (query: Query) => useQuery({ queryKey: attendanceKeys.progress(query), queryFn: () => attendanceApi.progress(query) });
export const useBranchSummary = (query: Query) => useQuery({ queryKey: attendanceKeys.summary(query), queryFn: () => attendanceApi.summary(query) });

export type { Page };
