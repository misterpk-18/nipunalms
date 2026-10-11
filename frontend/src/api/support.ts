import { download, get, list, post, upload, type Page } from "./client";
import type { DateTime, UserRef } from "./types";

export const SUPPORT_CATEGORIES = ["Academic", "LMS", "Account", "Recording access", "Device access", "Other"] as const;
export type SupportCategory = (typeof SUPPORT_CATEGORIES)[number];
export const SUPPORT_STATUSES = ["Open", "In Progress", "Waiting on Student", "Resolved", "Closed"] as const;
export type SupportStatus = (typeof SUPPORT_STATUSES)[number];

export type SupportAttachment = { attachment_id: number; filename: string; mime_type: string | null; size_bytes: number };

export type SupportMessage = {
  support_message_id: number;
  author: UserRef & { email: string | null };
  kind: "Message" | "Status" | "Escalation" | "Assignment" | "Reopened";
  body: string;
  is_internal: boolean;
  from_student: boolean;
  attachments: SupportAttachment[];
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
  escalation_level: "Branch Manager" | null;
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
  /** Raise a request; files (up to 3, 5 MB each) travel with it as a multipart form. */
  raise: (body: { category: SupportCategory; details: string; subject?: string; enrolment_id?: number | null; student_id?: number }, files: File[] = []) => {
    if (files.length === 0) return post<SupportDetail>("/support-requests", body);
    const form = new FormData();
    form.set("category", body.category);
    form.set("details", body.details);
    if (body.subject) form.set("subject", body.subject);
    files.forEach((file) => form.append("files", file));
    return upload<SupportDetail>("/support-requests", form);
  },
  message: (id: number, body: string, internal = false, files: File[] = []) => {
    if (files.length === 0) return post<SupportDetail>(`/support-requests/${id}/messages`, { body, internal });
    const form = new FormData();
    form.set("body", body);
    form.set("internal", String(internal));
    files.forEach((file) => form.append("files", file));
    return upload<SupportDetail>(`/support-requests/${id}/messages`, form);
  },
  downloadAttachment: (attachment: SupportAttachment) =>
    download(`/support-requests/attachments/${attachment.attachment_id}/download`, undefined, attachment.filename),
  status: (id: number, status: string, note?: string) => post<SupportDetail>(`/support-requests/${id}/status`, { status, note }),
  close: (id: number) => post<SupportDetail>(`/support-requests/${id}/close`),
  reopen: (id: number, reason: string) => post<SupportDetail>(`/support-requests/${id}/reopen`, { reason }),
  escalate: (id: number, reason: string) => post<SupportDetail>(`/support-requests/${id}/escalate`, { reason }),
  assign: (id: number, owner_user_id: number) => post<SupportDetail>(`/support-requests/${id}/assign`, { owner_user_id }),
  assignedStudents: () => get<AssignedStudent[]>("/trainer/students"),
};

/** What a student may attach: the same list the API enforces. */
export const ATTACHMENT_ACCEPT = ".png,.jpg,.jpeg,.pdf,.txt,.doc,.docx";
export const ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024;
export const ATTACHMENT_MAX_FILES = 3;
