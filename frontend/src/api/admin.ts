/** Super Admin API: Setup & health, users & access, student accounts, CRM sync, audit log, AI controls, calendar, Needs action. */
import { download, get, list, patch, post, type Page, type Query } from "./client";
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

export type ReadinessUpdate = Partial<Pick<ReadinessFields, "configuration_status" | "verification_status" | "owner" | "evidence" | "notes">> & {
  state?: SetupState;
  owner_user_id?: number | null;
};

// ---------------------------------------------------------------- setup & health (the two registers as one checklist)

export const SETUP_STATES = ["Not set up", "Set up", "Working", "Broken"] as const;
export type SetupState = (typeof SETUP_STATES)[number];

export type SetupItem = {
  key: string;
  kind: "integration" | "security";
  id: number;
  code: string;
  name: string;
  group: string;
  requirement: string;
  state: SetupState;
  owner: { user_id: number | null; full_name: string | null; label: string };
  evidence: string | null;
  notes: string | null;
  verified_at: DateTime | null;
  last_checked_at: DateTime | null;
};
export type SetupSummary = { counts: Record<SetupState, number>; total: number; open: number; done: boolean };
export type SetupChecklist = { items: SetupItem[]; summary: SetupSummary; help: Record<SetupState, string> };
export type StaffOption = { user_id: number; full_name: string; email: string | null; roles: string[] };

// ---------------------------------------------------------------- home: Needs action

export type NeedsActionRow = {
  key: string;
  kind: string;
  count: number;
  what: string;
  where: string | null;
  age_days: number | null;
  to: string;
  search: Record<string, unknown>;
  action: string;
  retry?: { crm_event_id: number } | null;
};
export type NeedsAction = {
  rows: NeedsActionRow[];
  total: number;
  setup: SetupSummary & { items: { key: string; name: string; group: string; state: SetupState; owner: string }[] };
};

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
  locked_until: DateTime | null;
  last_login_at: DateTime | null;
  password_changed_at: DateTime | null;
  created_at: DateTime;
  scopes: StaffScope[];
};

/** What happened to the message that carries a link: Queued / Sent, or Skipped / Failed with the reason. */
export type WhatsappOutcome = { state: string; note: string | null };

/** Create and reset carry the temporary password exactly once; create and invite also carry the one-time invite link. */
export type StaffUserWithPassword = StaffUser & {
  temporary_password?: string;
  invite_path?: string;
  invite_expires_at?: DateTime;
  whatsapp?: WhatsappOutcome;
};

export type ScopeInput = { role_code: RoleCode; branch_id?: number | null; expires_at?: DateTime | null };
export type UserFilters = { q?: string; role_code?: string; branch_id?: string; is_active?: string; locked?: string; page?: number };

// ---------------------------------------------------------------- student accounts

export type SuggestedStep = {
  code: string;
  label: string;
  detail: string;
  action: "send_link" | "reactivate" | "open" | "issues" | null;
  action_label: string | null;
  attention: boolean;
};

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
  suggested_step: SuggestedStep;
  needs_attention: boolean;
};

/** Where a record opens, for the router: `to` with its `search` or `params`. */
export type RecordLink = { to: string; search?: Record<string, unknown>; params?: Record<string, unknown> };

export type AuditEntry = {
  audit_id: number;
  /** One plain sentence about what happened, and the name and link of the record it is about (null when there is none). */
  sentence: string;
  target: string | null;
  link: RecordLink | null;
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
  activation: {
    status: "valid" | "expired" | "used" | "revoked";
    expires_at: DateTime;
    issued_at: DateTime;
    channel: string;
    whatsapp: WhatsappOutcome | null;
  } | null;
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
  whatsapp: WhatsappOutcome;
};
export type StudentFilters = {
  q?: string;
  activation_status?: string;
  activation_channel?: string;
  branch_id?: string;
  needs_attention?: string;
  page?: number;
};

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
  /** Plain words: what the event is, what it is about, and for a failed one why it failed and whether Retry can work. */
  label: string;
  summary: string;
  plain_cause: string | null;
  can_retry: boolean;
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
  needs_attention: number;
  pending_outbox: number;
  last_event_received_at: DateTime | null;
  last_outbox_delivered_at: DateTime | null;
  oldest_pending_outbox_at: DateTime | null;
  event_types: string[];
  outbox_event_types: string[];
};
export type EventFilters = { status?: string; event_type?: string; q?: string; attention?: string; from?: string; to?: string; page?: number };
export type OutboxFilters = { status?: string; event_type?: string; page?: number };

export type AuditFilters = {
  actor_user_id?: string;
  entity_type?: string;
  entity_id?: string;
  action?: string;
  preset?: string;
  from?: string;
  to?: string;
  page?: number;
};
export type AuditFacets = {
  actions: string[];
  entity_types: string[];
  actors: { user_id: number; full_name: string; email: string | null }[];
  presets: { key: string; label: string }[];
};

// ---------------------------------------------------------------- AI controls

export type AiAudience = "All" | "Student" | "Staff";
export type AiControl = {
  control_id: number;
  audience: AiAudience;
  branch_id: number | null;
  reason: string;
  remediation: string | null;
  disabled_by_name: string;
  disabled_at: DateTime;
  restored_by_name: string | null;
  restored_at: DateTime | null;
  restoration_note: string | null;
  active: boolean;
};
export type AiStatus = {
  audiences: { audience: "Student" | "Staff"; label: string; state: "On" | "Off"; control: AiControl | null; via_all: boolean }[];
  all: { state: "On" | "Off"; control: AiControl | null };
  branches: AiControl[];
  can_switch: boolean;
};

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
  setup: ["admin", "setup"] as const,
  needsAction: ["admin", "needs-action"] as const,
  staffOptions: ["admin", "staff-options"] as const,
  aiStatus: ["admin", "ai-status"] as const,
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
  sendInvite: (id: number) => post<StaffUserWithPassword>(`/admin/users/${id}/invite`),
  unlockUser: (id: number, reason: string) => post<StaffUser>(`/admin/users/${id}/unlock`, { reason }),

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
  auditFacets: () => get<AuditFacets>("/audit-log/facets"),
  exportAudit: (filters: AuditFilters) => download("/audit-log/export", { ...filters, page: undefined } as Query, "audit-log.csv"),

  setup: () => get<SetupChecklist>("/admin/setup"),
  needsAction: () => get<NeedsAction>("/admin/needs-action"),
  staffOptions: () => get<StaffOption[]>("/admin/staff-options"),
  aiStatus: () => get<AiStatus>("/ai-controls/status"),
  switchAiOff: (body: { audience: AiAudience; branch_id: number | null; reason: string; remediation?: string }) => post<AiControl>("/ai-controls", body),
  restoreAi: (id: number, restoration_note: string) => post<AiControl>(`/ai-controls/${id}/restore`, { restoration_note }),
  branches: () => get<(BranchRef & { is_active?: boolean })[]>("/reference/branches"),
};
