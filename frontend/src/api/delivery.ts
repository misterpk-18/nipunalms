/** Delivery slice: curriculum, batches, allocation, class sessions, Meet association and the learner's course views. */
import { del, get, list, patch, post, put, type Query } from "./client";
import type { BranchRef, DateOnly, DateTime, UserRef } from "./types";

export type CourseRef = { course_id: number; course_code: string; title: string };
export type BatchRef = { batch_id: number; batch_code: string; course_code: string };
export type VersionRef = { curriculum_version_id: number; version_label: string; status: string };
export type Trainer = {
  batch_trainer_id: number;
  user_id: number;
  full_name: string;
  role: "Lead" | "Co-trainer";
  from_date: DateOnly;
  to_date: DateOnly | null;
};
export type Delivery = { delivered: number; upcoming: number; cancelled: number; planned: number; percent: number | null };

// ---------------------------------------------------------------- curriculum

export type TopicRow = { topic_id: number; title: string; title_te: string | null; sort_order: number; is_required: boolean };
export type ModuleContent = { module_id: number; title: string; title_te: string | null; sort_order: number; topics: TopicRow[] };
export type Component = { component_id: number; track_code: string; track_name: string; role: string; sort_order: number };
export type CurriculumRow = {
  course: CourseRef & { is_combo: boolean };
  component: Component | null;
  active_version: VersionRef | null;
  latest_version: VersionRef | null;
  readiness: string;
  pending_enrolments: number;
  borrowed_from: CourseRef | null;
};
export type CurriculumEvent = {
  event_id: number;
  action: string;
  from_status: string | null;
  to_status: string;
  actor: UserRef | null;
  note: string | null;
  created_at: DateTime;
};
export type CurriculumVersion = VersionRef & {
  course: CourseRef;
  component: Component | null;
  approved_at: DateTime | null;
  created_at: DateTime;
  counts: { modules: number; topics: number; required_topics: number };
  usage: { batches: number; enrolments: number; tracks: number };
  modules?: ModuleContent[];
  events?: CurriculumEvent[];
  blockers?: string[];
  released?: { enrolments_released: number; batches_mapped: number };
};

// ---------------------------------------------------------------- batches

export type Batch = {
  batch_id: number;
  batch_code: string;
  crm_batch_id: string | null;
  course: CourseRef;
  branch: BranchRef;
  curriculum_version: VersionRef | null;
  capacity: number;
  allocated_count: number;
  is_full: boolean;
  mode: string;
  planned_start: DateOnly | null;
  planned_end: DateOnly | null;
  /** The timetable sales can promise: days in week order, IST "HH:MM", the room (none for Live Online). */
  schedule_days: string[];
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  state: string;
  readiness: string;
  readiness_reason: string | null;
  recovery_owner: string | null;
  trainers: Trainer[];
};
export type BatchEvent = {
  event_id: number;
  event_type: string;
  from_value: string | null;
  to_value: string | null;
  reason: string | null;
  actor: UserRef | null;
  created_at: DateTime;
};
export type BatchDetail = Batch & {
  session_counts: { delivered: number; upcoming: number; cancelled: number };
  trainer_history: Trainer[];
  history: BatchEvent[];
};
export type Check = { key: string; label: string; status: "pass" | "fail" | "pending" | "warn"; detail: string };
export type Readiness = {
  batch_id: number;
  readiness: string;
  readiness_reason: string | null;
  recovery_owner: string | null;
  checks: Check[];
  suggested: { readiness: string; readiness_reason: string | null; recovery_owner: string | null };
};
export type AllocationReview = {
  enrolment: { enrolment_id: number; enrolment_code: string };
  batch: BatchRef;
  checks: Check[];
  result: "Ready to allocate" | "Review needed" | "Blocked";
  blocking: string[];
  warnings: string[];
  recovery_owner: string | null;
};
export type Allocation = {
  allocation_id: number;
  enrolment_id: number;
  batch: BatchRef;
  status: string;
  effective_from: DateOnly;
  effective_to: DateOnly | null;
  reason: string | null;
};
export type RosterRow = Allocation & {
  student: { student_id: number; student_code: string; full_name: string };
  enrolment: { enrolment_id: number; enrolment_code: string; status: string; kind: string; joining_date: DateOnly | null; mode: string };
};
export type EnrolmentRow = {
  enrolment_id: number;
  enrolment_code: string;
  course: CourseRef;
  kind: string;
  status: string;
  mode: string;
  joining_date: DateOnly | null;
  service_branch: BranchRef;
  admission: { admission_code: string };
  curriculum_version: VersionRef | null;
  batch: BatchRef | null;
  student: { student_id: number; student_code: string; full_name: string };
  waiting_days?: number;
  open_batches?: (BatchRef & { capacity: number; state: string })[];
};

// ---------------------------------------------------------------- sessions

export type Join = { enabled: boolean; reason: string | null; url: string | null };
export type ClassSession = {
  session_id: number;
  session_code: string;
  batch: BatchRef;
  branch: BranchRef;
  course: CourseRef;
  topic: { topic_id: number; title: string; module_id: number } | null;
  title: string;
  starts_at: DateTime;
  ends_at: DateTime;
  mode: string;
  trainer: UserRef;
  room: string | null;
  meet_link: string | null;
  meet_status: string;
  meet_status_label: string;
  organizer_email: string | null;
  join: Join | null;
  state: string;
  delivered_at: DateTime | null;
  notes: string | null;
  open_request_id?: number | null;
  changes_count?: number;
  enrolment?: { enrolment_id: number; enrolment_code: string } | null;
};
export type SessionChange = {
  change_id: number;
  change_type: string;
  reason: string;
  old_starts_at: DateTime;
  old_ends_at: DateTime;
  new_starts_at: DateTime | null;
  new_ends_at: DateTime | null;
  new_trainer: UserRef | null;
  notice_hours: string;
  short_notice: boolean;
  changed_by: UserRef | null;
  created_at: DateTime;
};
export type MeetEvent = {
  event_id: number;
  event_type: string;
  meet_status: string;
  organizer_email: string | null;
  meet_link: string | null;
  detail: string | null;
  actor: UserRef | null;
  created_at: DateTime;
};
export type RescheduleRequest = {
  request_id: number;
  session: { session_id: number; session_code: string; title: string; starts_at: DateTime; ends_at: DateTime; state: string; batch: BatchRef };
  requested_by: UserRef;
  proposed_starts_at: DateTime;
  proposed_ends_at: DateTime;
  reason: string;
  status: string;
  decided_by: UserRef | null;
  decision_note: string | null;
  created_at: DateTime;
};
export type SessionDetail = ClassSession & {
  allocated_count: number;
  topic_path: { topic_id: number; title: string; module: { module_id: number; title: string } } | null;
  changes?: SessionChange[];
  meet_events?: MeetEvent[];
  open_request?: RescheduleRequest | null;
  organizer_note?: string;
};

// ---------------------------------------------------------------- learner views

export type MyEnrolment = {
  enrolment_id: number;
  enrolment_code: string;
  course: CourseRef;
  kind: string;
  status: string;
  admission: { admission_code: string };
  parent_enrolment_id: number | null;
  curriculum_version: VersionRef | null;
  service_branch: BranchRef;
  collecting_branch: BranchRef;
  mode: string;
  joining_date: DateOnly | null;
  access_start: DateOnly | null;
  access_end: DateOnly | null;
  certificate_status: string;
  batch: BatchRef | null;
  trainers: Trainer[];
  delivery: Delivery;
  explanation: string;
  linked_admission_code: string | null;
};
export type ModuleRow = {
  module_id: number;
  title: string;
  title_te: string | null;
  sort_order: number;
  topic_count: number;
  required_topic_count: number;
  session_count: number;
  delivered_count: number;
  status: string;
};
export type TrackRow = {
  enrolment_track_id: number;
  track_code: string;
  track_name: string;
  role: string;
  curriculum_version: VersionRef | null;
  delivery: Delivery;
};
export type MyEnrolmentDetail = MyEnrolment & {
  tracks: TrackRow[];
  modules: ModuleRow[];
  next_sessions: { session_id: number; title: string; starts_at: DateTime; ends_at: DateTime; state: string; mode: string; trainer: string }[];
  finance: { fee_total: string; verified_paid: string; balance: string; as_of: DateTime } | null;
};
export type TrackDetail = {
  enrolment: { enrolment_id: number; enrolment_code: string; course: CourseRef; curriculum_version: VersionRef | null };
  track: TrackRow;
  delivery: Delivery;
  modules: ModuleRow[];
};
type Context = { enrolment: { enrolment_id: number; enrolment_code: string; course: CourseRef }; track: TrackRow | null } | null;
type ModuleHead = { module_id: number; title: string; title_te: string | null; sort_order: number; curriculum_version: VersionRef; course_id: number };
export type ModulePage = ModuleHead & { context: Context; status: string | null; topics: (TopicRow & { session_count: number })[] };
export type TopicPage = TopicRow & {
  module: ModuleHead;
  context: Context;
  sessions: {
    session_id: number;
    session_code: string;
    title: string;
    starts_at: DateTime;
    ends_at: DateTime;
    state: string;
    mode: string;
    trainer: string;
    batch: BatchRef;
  }[];
};

// ---------------------------------------------------------------- calls

export const deliveryApi = {
  // curriculum
  curriculumOverview: () => get<CurriculumRow[]>("/curriculum/overview"),
  versions: (query: Query) => get<CurriculumVersion[]>("/curriculum-versions", query),
  curriculumVersion: (id: number) => get<CurriculumVersion>(`/curriculum-versions/${id}`),
  createVersion: (body: { course_id: number; component_id?: number | null; version_label: string; copy_from_version_id?: number | null }) =>
    post<CurriculumVersion>("/curriculum-versions", body),
  renameVersion: (id: number, version_label: string) => patch<CurriculumVersion>(`/curriculum-versions/${id}`, { version_label }),
  deleteVersion: (id: number) => del<null>(`/curriculum-versions/${id}`),
  versionAction: (id: number, action: "submit" | "return" | "approve" | "activate" | "retire", body: { reason?: string } = {}) =>
    post<CurriculumVersion>(`/curriculum-versions/${id}/${action}`, body),
  addModule: (versionId: number, body: { title: string; title_te?: string }) => post<ModuleContent>(`/curriculum-versions/${versionId}/modules`, body),
  updateModule: (id: number, body: { title?: string; title_te?: string | null; position?: number }) => patch<ModuleContent>(`/curriculum-modules/${id}`, body),
  deleteModule: (id: number) => del<null>(`/curriculum-modules/${id}`),
  addTopic: (moduleId: number, body: { title: string; is_required?: boolean }) => post<TopicRow>(`/curriculum-modules/${moduleId}/topics`, body),
  updateTopic: (id: number, body: { title?: string; is_required?: boolean; position?: number }) => patch<TopicRow>(`/curriculum-topics/${id}`, body),
  deleteTopic: (id: number) => del<null>(`/curriculum-topics/${id}`),

  // batches
  batches: (query: Query) => list<Batch>("/batches", { per_page: 100, ...query }),
  batch: (id: number) => get<BatchDetail>(`/batches/${id}`),
  createBatch: (body: Record<string, unknown>) => post<Batch>("/batches", body),
  updateBatch: (id: number, body: Record<string, unknown>) => patch<Batch>(`/batches/${id}`, body),
  batchState: (id: number, body: { state: string; reason?: string }) => post<Batch>(`/batches/${id}/state`, body),
  readiness: (id: number) => get<Readiness>(`/batches/${id}/readiness`),
  setReadiness: (id: number, body: { readiness: string; readiness_reason?: string | null; recovery_owner?: string | null }) =>
    patch<Readiness>(`/batches/${id}/readiness`, body),
  assignTrainer: (id: number, body: { trainer_user_id: number; role: string }) => post<Trainer>(`/batches/${id}/trainers`, body),
  trainerRole: (id: number, assignmentId: number, role: string) => patch<Trainer>(`/batches/${id}/trainers/${assignmentId}`, { role }),
  endTrainer: (id: number, assignmentId: number) => del<Trainer>(`/batches/${id}/trainers/${assignmentId}`),
  roster: (id: number, query: Query = {}) => list<RosterRow>(`/batches/${id}/allocations`, { per_page: 100, ...query }),
  review: (batchId: number, enrolmentId: number, transfer = false) =>
    get<AllocationReview>(`/batches/${batchId}/allocation-review`, { enrolment_id: enrolmentId, transfer }),
  allocate: (batchId: number, body: { enrolment_id: number; reason?: string; acknowledge_warnings?: boolean }) =>
    post<Allocation>(`/batches/${batchId}/allocations`, body),
  transfer: (enrolmentId: number, body: { batch_id: number; reason: string; acknowledge_warnings?: boolean }) =>
    post<Allocation>(`/enrolments/${enrolmentId}/transfer`, body),
  deallocate: (enrolmentId: number, reason: string) => post<Allocation>(`/enrolments/${enrolmentId}/deallocate`, { reason }),
  enrolments: (query: Query) => list<EnrolmentRow>("/enrolments", { per_page: 100, ...query }),
  allocationQueue: (query: Query = {}) => list<EnrolmentRow>("/allocation-queue", { per_page: 100, ...query }),
  staff: (role: string, branchId: number) => get<{ user_id: number; full_name: string }[]>("/reference/staff", { role, branch_id: branchId }),
  courses: () => get<(CourseRef & { is_combo: boolean })[]>("/reference/courses"),

  // sessions
  sessions: (query: Query) => list<ClassSession>("/class-sessions", { per_page: 100, ...query }),
  session: (id: number) => get<SessionDetail>(`/class-sessions/${id}`),
  createSessions: (body: Record<string, unknown>) => post<ClassSession[]>("/class-sessions", body),
  updateSession: (id: number, body: Record<string, unknown>) => patch<ClassSession>(`/class-sessions/${id}`, body),
  reschedule: (id: number, body: { starts_at: string; ends_at: string; reason: string; acknowledge_room_conflict?: boolean }) =>
    post<ClassSession>(`/class-sessions/${id}/reschedule`, body),
  cancelSession: (id: number, reason: string) => post<ClassSession>(`/class-sessions/${id}/cancel`, { reason }),
  startSession: (id: number) => post<ClassSession>(`/class-sessions/${id}/start`),
  deliverSession: (id: number, notes?: string) => post<ClassSession>(`/class-sessions/${id}/deliver`, { notes }),
  meetLink: (id: number, meet_link: string) => put<ClassSession>(`/class-sessions/${id}/meet`, { meet_link }),
  meetFailed: (id: number, detail: string) => post<ClassSession>(`/class-sessions/${id}/meet/fail`, { detail }),
  meetReset: (id: number) => post<ClassSession>(`/class-sessions/${id}/meet/reset`),
  requests: (query: Query) => list<RescheduleRequest>("/reschedule-requests", { per_page: 100, ...query }),
  requestReschedule: (id: number, body: { proposed_starts_at: string; proposed_ends_at: string; reason: string }) =>
    post<RescheduleRequest>(`/class-sessions/${id}/reschedule-requests`, body),
  approveRequest: (id: number, note?: string) => post<RescheduleRequest>(`/reschedule-requests/${id}/approve`, { note }),
  rejectRequest: (id: number, note: string) => post<RescheduleRequest>(`/reschedule-requests/${id}/reject`, { note }),

  // learner
  myEnrolments: () => get<MyEnrolment[]>("/me/enrolments"),
  myEnrolment: (id: number) => get<MyEnrolmentDetail>(`/me/enrolments/${id}`),
  myTrack: (id: number, trackId: number) => get<TrackDetail>(`/me/enrolments/${id}/tracks/${trackId}`),
  mySchedule: (query: Query) => list<ClassSession>("/me/schedule", { per_page: 100, ...query }),
  module: (id: number) => get<ModulePage>(`/modules/${id}`),
  topic: (id: number) => get<TopicPage>(`/topics/${id}`),
};
