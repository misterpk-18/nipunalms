import { get, list, post, type Page } from "./client";
import type { DateTime, UserRef } from "./types";

export const SUPPORT_CATEGORIES = ["Academic", "LMS", "Account", "Recording access", "Device access", "Other"] as const;
export type SupportCategory = (typeof SUPPORT_CATEGORIES)[number];
export const SUPPORT_STATUSES = ["Open", "In Progress", "Waiting on Student", "Resolved", "Closed"] as const;
export type SupportStatus = (typeof SUPPORT_STATUSES)[number];

export type SupportMessage = {
  support_message_id: number;
  author: UserRef & { email: string | null };
  kind: "Message" | "Status" | "Escalation" | "Assignment" | "Reopened";
  body: string;
  is_internal: boolean;
  from_student: boolean;
  created_at: DateTime;
};

export type SupportSummary = {
  support_request_id: number;
  request_code: string;
  student: { student_id: number; student_code: string; full_name: string };
  enrolment: { enrolment_id: number; enrolment_code: string } | null;
  branch: { branch_id: number; branch_code: string; branch_name: string };
  category: SupportCategory;
  subject: string;
  priority: "Normal" | "High" | "Urgent";
  status: SupportStatus;
  raised_via: "Student" | "Staff flag";
  raised_by: UserRef;
  owner: UserRef & { role_code: string; label: string };
  escalation_level: "Academic Coordinator" | "Branch Manager" | null;
  escalated_at: DateTime | null;
  sla_due_at: DateTime;
  sla_breached: boolean;
  created_at: DateTime;
  updated_at: DateTime;
};

export type SupportDetail = SupportSummary & {
  escalation_reason: string | null;
  resolution_note: string | null;
  resolved_at: DateTime | null;
  closed_at: DateTime | null;
  reopened_count: number;
  messages: SupportMessage[];
};

export type SupportFilters = { status?: string; category?: string; escalated?: boolean; open?: boolean; mine?: boolean; q?: string; page?: number };

export type AssignedStudent = {
  student: { student_id: number; student_code: string; full_name: string };
  batch: { batch_id: number; batch_code: string; course_code: string };
  enrolment: { enrolment_id: number; enrolment_code: string };
  open_requests: SupportSummary[];
  flag: string;
};

export const supportApi = {
  list: (filters: SupportFilters = {}): Promise<Page<SupportSummary>> => list<SupportSummary>("/support-requests", filters),
  get: (id: number) => get<SupportDetail>(`/support-requests/${id}`),
  raise: (body: { category: SupportCategory; details: string; subject?: string; enrolment_id?: number | null; student_id?: number }) =>
    post<SupportDetail>("/support-requests", body),
  message: (id: number, body: string, internal = false) => post<SupportDetail>(`/support-requests/${id}/messages`, { body, internal }),
  status: (id: number, status: string, note?: string) => post<SupportDetail>(`/support-requests/${id}/status`, { status, note }),
  close: (id: number) => post<SupportDetail>(`/support-requests/${id}/close`),
  reopen: (id: number, reason: string) => post<SupportDetail>(`/support-requests/${id}/reopen`, { reason }),
  escalate: (id: number, reason: string) => post<SupportDetail>(`/support-requests/${id}/escalate`, { reason }),
  assign: (id: number, owner_user_id: number) => post<SupportDetail>(`/support-requests/${id}/assign`, { owner_user_id }),
  assignedStudents: () => get<AssignedStudent[]>("/trainer/students"),
};
