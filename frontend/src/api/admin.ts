/** Super Admin API: integration / security readiness, users & access, student accounts, CRM sync monitor, audit log. */
import { get, list, patch, post, type Page } from "./client";
import type { BranchRef, DateTime, DateOnly, RoleCode } from "./types";

// ---------------------------------------------------------------- readiness registers

export const CONFIGURATION_STATUSES = ["Not Configured", "Configuration Pending", "Configured", "Misconfigured"] as const;
export const VERIFICATION_STATUSES = ["Not Verified", "Pending Verification", "Verified", "Failed"] as const;

export type ConfigurationStatus = (typeof CONFIGURATION_STATUSES)[number];
export type VerificationStatus = (typeof VERIFICATION_STATUSES)[number];

export type ReadinessFields = {
  requirement: string;
  configuration_status: ConfigurationStatus;
  verification_status: VerificationStatus;
  owner: string;
  evidence: string | null;
  notes: string | null;
  verified_by: number | null;
  verified_at: DateTime | null;
  last_checked_at: DateTime | null;
};

export type Integration = ReadinessFields & { integration_id: number; integration_code: string; integration_name: string };
export type SecurityControl = ReadinessFields & { control_id: number; control_code: string; category: string; title: string };

export type ReadinessUpdate = Partial<Pick<ReadinessFields, "configuration_status" | "verification_status" | "owner" | "evidence" | "notes">>;

// ---------------------------------------------------------------- users & access

export type StaffScope = {
  scope_id: number;
  role_code: RoleCode;
  role_name: string;
  branch_id: number | null;
  branch_code: string | null;
  branch_name: string | null;
  is_company_wide: boolean;
  expires_at: DateTime | null;
  granted_at: DateTime;
};

export type StaffUser = {
  user_id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  must_change_password: boolean;
  is_locked: boolean;
  last_login_at: DateTime | null;
  password_changed_at: DateTime | null;
  created_at: DateTime;
  scopes: StaffScope[];
};

/** Create / reset responses carry the temporary password exactly once. */
export type StaffUserWithPassword = StaffUser & { temporary_password: string };

export type ScopeInput = { role_code: RoleCode; branch_id?: number | null; expires_at?: DateTime | null };
export type UserFilters = { q?: string; role_code?: string; branch_id?: string; is_active?: string; page?: number };

// ---------------------------------------------------------------- student accounts

export type StudentAccount = {
  student_id: number;
  student_code: string;
  full_name: string;
  name_te: string | null;
  email: string | null;
  lms_user_id: string;
  activation_status: "Account Created" | "Activation Pending" | "Activated" | "Suspended";
  service_branch: BranchRef;
  provisioned_at: DateTime | null;
  user_id: number | null;
  has_password: boolean;
  is_login_active: boolean;
  last_login_at: DateTime | null;
  active_sessions: number;
  enrolment_counts: Record<string, number>;
  enrolment_total: number;
};

export type AuditEntry = {
  audit_id: number;
  occurred_at: DateTime;
  actor_user_id: number | null;
  actor?: { user_id: number; full_name: string; email: string | null } | null;
  action: string;
  entity_type: string;
  entity_id: string;
  branch_id: number | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  reason: string | null;
};

export type StudentAccountDetail = StudentAccount & {
  enrolments: {
    enrolment_id: number;
    enrolment_code: string;
    course_code: string;
    course_title: string;
    kind: string;
    status: string;
    service_branch_id: number;
    joining_date: DateOnly | null;
  }[];
  activation: { status: "valid" | "expired" | "used" | "revoked"; expires_at: DateTime; issued_at: DateTime; channel: string } | null;
  suspension: { suspended_at: DateTime; reason: string | null } | null;
  audit: AuditEntry[];
};

export type ActivationIssued = {
  student_id: number;
  student_code: string;
  token: string;
  activation_path: string;
  expires_at: DateTime;
  activation_status: string;
};
export type StudentFilters = { q?: string; activation_status?: string; branch_id?: string; page?: number };

// ---------------------------------------------------------------- CRM sync

export const CRM_EVENT_STATUSES = ["Received", "Applied", "Ignored — stale", "Failed"] as const;
export const OUTBOX_STATUSES = ["Pending", "Delivered", "Failed"] as const;

export type CrmEvent = {
  crm_event_id: number;
  event_id: string;
  event_type: string;
  source_version: number;
  occurred_at: DateTime;
  status: (typeof CRM_EVENT_STATUSES)[number];
  error: string | null;
  retries: number;
  received_at: DateTime;
  processed_at: DateTime | null;
  payload?: unknown;
  result?: unknown;
};

export type CrmOutboxRow = {
  outbox_id: number;
  event_id: string;
  event_type: string;
  payload: unknown;
  status: (typeof OUTBOX_STATUSES)[number];
  attempts: number;
  last_error: string | null;
  created_at: DateTime;
  delivered_at: DateTime | null;
};

export type CrmSyncSummary = {
  events: Record<string, number>;
  outbox: Record<string, number>;
  failed_events: number;
  pending_outbox: number;
  last_event_received_at: DateTime | null;
  last_outbox_delivered_at: DateTime | null;
  oldest_pending_outbox_at: DateTime | null;
  event_types: string[];
  outbox_event_types: string[];
};
export type EventFilters = { status?: string; event_type?: string; q?: string; from?: string; to?: string; page?: number };
export type OutboxFilters = { status?: string; event_type?: string; page?: number };

export type AuditFilters = { actor_user_id?: string; entity_type?: string; entity_id?: string; action?: string; from?: string; to?: string; page?: number };

// ---------------------------------------------------------------- calls

export const adminKeys = {
  integrations: ["admin", "integrations"] as const,
  controls: ["admin", "security-controls"] as const,
  users: (filters: UserFilters) => ["admin", "users", filters] as const,
  usersAll: ["admin", "users"] as const,
  students: (filters: StudentFilters) => ["admin", "students", filters] as const,
  studentsAll: ["admin", "students"] as const,
  student: (id: number) => ["admin", "student", id] as const,
  syncSummary: ["admin", "crm-sync", "summary"] as const,
  syncEvents: (filters: EventFilters) => ["admin", "crm-sync", "events", filters] as const,
  syncEvent: (id: number) => ["admin", "crm-sync", "event", id] as const,
  syncOutbox: (filters: OutboxFilters) => ["admin", "crm-sync", "outbox", filters] as const,
  syncAll: ["admin", "crm-sync"] as const,
  audit: (filters: AuditFilters) => ["admin", "audit", filters] as const,
  auditFacets: ["admin", "audit", "facets"] as const,
};

export const adminApi = {
  integrations: () => get<Integration[]>("/integrations"),
  updateIntegration: (id: number, body: ReadinessUpdate) => patch<Integration>(`/integrations/${id}`, body),
  controls: () => get<SecurityControl[]>("/security-controls"),
  updateControl: (id: number, body: ReadinessUpdate) => patch<SecurityControl>(`/security-controls/${id}`, body),

  users: (filters: UserFilters): Promise<Page<StaffUser>> => list<StaffUser>("/admin/users", { ...filters, per_page: 25 }),
  createUser: (body: { full_name: string; email: string; phone?: string; scopes: ScopeInput[] }) => post<StaffUserWithPassword>("/admin/users", body),
  updateUser: (id: number, body: { full_name?: string; email?: string; phone?: string | null }) => patch<StaffUser>(`/admin/users/${id}`, body),
  grantScope: (id: number, body: ScopeInput) => post<StaffUser>(`/admin/users/${id}/scopes`, body),
  revokeScope: (id: number, scopeId: number, reason: string) => post<StaffUser>(`/admin/users/${id}/scopes/${scopeId}/revoke`, { reason }),
  deactivateUser: (id: number, reason: string) => post<StaffUser>(`/admin/users/${id}/deactivate`, { reason }),
  reactivateUser: (id: number, reason?: string) => post<StaffUser>(`/admin/users/${id}/reactivate`, { reason }),
  resetPassword: (id: number) => post<StaffUserWithPassword>(`/admin/users/${id}/reset-password`),

  students: (filters: StudentFilters): Promise<Page<StudentAccount>> => list<StudentAccount>("/admin/students", { ...filters, per_page: 25 }),
  student: (id: number) => get<StudentAccountDetail>(`/admin/students/${id}`),
  issueActivation: (id: number) => post<ActivationIssued>(`/students/${id}/activation`),
  suspendStudent: (id: number, reason: string) => post<StudentAccount>(`/admin/students/${id}/suspend`, { reason }),
  reactivateStudent: (id: number, reason?: string) => post<StudentAccount>(`/admin/students/${id}/reactivate`, { reason }),
  revokeStudentSessions: (id: number, reason?: string) => post<{ sessions_ended: number }>(`/admin/students/${id}/revoke-sessions`, { reason }),

  syncSummary: () => get<CrmSyncSummary>("/admin/crm-sync/summary"),
  syncEvents: (filters: EventFilters): Promise<Page<CrmEvent>> => list<CrmEvent>("/admin/crm-sync/events", { ...filters, per_page: 25 }),
  syncEvent: (id: number) => get<CrmEvent>(`/admin/crm-sync/events/${id}`),
  retryEvent: (id: number) => post<CrmEvent>(`/admin/crm-sync/events/${id}/retry`),
  syncOutbox: (filters: OutboxFilters): Promise<Page<CrmOutboxRow>> => list<CrmOutboxRow>("/admin/crm-sync/outbox", { ...filters, per_page: 25 }),

  audit: (filters: AuditFilters): Promise<Page<AuditEntry>> => list<AuditEntry>("/audit-log", { ...filters, per_page: 25 }),
  auditFacets: () => get<{ actions: string[]; entity_types: string[] }>("/audit-log/facets"),
  branches: () => get<(BranchRef & { is_active?: boolean })[]>("/reference/branches"),
};
