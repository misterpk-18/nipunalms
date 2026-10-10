/** Delivery slice: curriculum, batches, allocation, class sessions, Meet association and the learner's course views. */
import { del, get, list, patch, post, put, type Query } from "./client";
import type { Assignment, TestItem } from "./assessments";
import type { StudentRecording, StudentResource } from "./content";
import type { BranchRef, DateOnly, DateTime, UserRef } from "./types";

export type CourseRef = { course_id: number; course_code: string; title: string };
export type BatchRef = { batch_id: number; batch_code: string; course_code: string; display_name?: string | null };
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

export type TopicClass = "Required" | "Recommended" | "Optional";
export type TopicRow = {
  topic_id: number;
  title: string;
  title_te: string | null;
  sort_order: number;
  is_required: boolean;
  topic_class: TopicClass;
  outcome: string | null;
  instructional_minutes: number | null;
  independent_minutes: number | null;
  weight: string | null;
  evidence: string | null;
  activities: string | null;
  depends_on: number[];
};
export type ModuleContent = {
  module_id: number;
  title: string;
  title_te: string | null;
  sort_order: number;
  library_version_id: number | null;
  topics: TopicRow[];
};
export type Component = {
  component_id: number;
  track_code: string;
  track_name: string;
  role: string;
  sort_order: number;
  component_course?: CourseRef | null;
  equivalence_note?: string | null;
  equivalence_reviewed_at?: DateTime | null;
};
export type CompletionProfile = { attendance_minimum_pct: number; pass_mark_pct: number; recovery_rule: string; reassessment_rule: string };
export type VersionTotals = {
  instructional_minutes: number;
  independent_minutes: number;
  total_minutes: number;
  unestimated_topics: number;
  hours_verified: boolean;
  hours_verified_at: DateTime | null;
  booster: { track_code: string; instructional_minutes: number; independent_minutes: number; total_minutes: number } | null;
};
export type AssessmentRequirement = {
  requirement_id: number;
  kind: "Assignment" | "Test";
  title: string;
  outcome: string;
  weight: string;
  pass_rule: string;
  counts_for_completion: boolean;
  module_id: number | null;
  topic_id: number | null;
};
type Decided = {
  status: "Pending" | "Approved" | "Rejected";
  requested_by: UserRef;
  requested_at: DateTime;
  decided_by: UserRef | null;
  decision_note: string | null;
};
export type AcademicMapping = Decided & {
  mapping_id: number;
  enrolment_id: number;
  from_version: VersionRef | null;
  to_version: VersionRef;
  comparison: string;
  migration_plan: string;
  trainer_evidence: string | null;
  student_acceptance: string | null;
  proposed_credits: { topic_id: number; original_evidence: string }[];
};
export type EquivalenceRule = Decided & { rule_id: number; from_version_id: number; to_version_id: number; description: string };
export type CurriculumVariation = Decided & {
  variation_id: number;
  curriculum_version_id: number;
  branch_id: number;
  batch_id: number | null;
  topic_id: number | null;
  kind: string;
  description: string;
  remedial_plan: string | null;
};
export type LibraryVersion = {
  library_version_id: number;
  version_no: number;
  content: { title: string; topics: { title: string }[] };
  change_note: string | null;
  status: "Pending" | "Approved" | "Rejected";
  proposed_by: number;
};
export type LibraryModule = {
  library_module_id: number;
  module_code: string;
  title: string;
  current_version: LibraryVersion | null;
  versions: LibraryVersion[];
};
export type CurriculumRow = {
  course: CourseRef & { is_combo: boolean };
  component: Component | null;
  active_version: VersionRef | null;
  latest_version: VersionRef | null;
  readiness: string;
  waiting_batches: number;
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
  totals?: VersionTotals;
  completion_profile?: CompletionProfile | null;
  assessment_requirements?: AssessmentRequirement[];
  components?: { component_id: number; component_version: VersionRef }[];
};

// ---------------------------------------------------------------- batches

export const BATCH_STATES = ["Forming", "Proposed", "Starting", "Running", "Full", "On Hold", "Completed", "Cancelled", "Archived"] as const;
export type BatchType = "Group" | "Individual" | "Corporate";
export type SchedulePattern = "Regular" | "Weekend" | "Fast-track";
export type RecordingProvision = "Included" | "Not Included" | "Limited";
export type Batch = {
  batch_id: number;
  batch_code: string;
  display_name: string | null;
  crm_batch_id: string | null;
  course: CourseRef;
  component: { component_id: number; track_code: string; track_name: string } | null;
  branch: BranchRef;
  creating_branch: BranchRef;
  batch_type: BatchType;
  schedule_pattern: SchedulePattern;
  classroom_capacity: number | null;
  lab_capacity: number | null;
  online_capacity: number | null;
  recording_provision: RecordingProvision | null;
  recording_terms: string | null;
  proposed_by: UserRef | null;
  proposed_at: DateTime | null;
  proposal_note: string | null;
  confirmed_by: UserRef | null;
  confirmed_at: DateTime | null;
  held_from_state: string | null;
  meet_series_link: string | null;
  meet_space_id: string | null;
  calendar_series_id: string | null;
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
  /** What to show: Draft / Proposed / Confirmed / In Progress / In Progress (Full) / On Hold / Completed / Cancelled / Archived. */
  state_label: string;
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
  successions: BatchSuccession[];
  handovers: BatchHandover[];
};
export type Check = { key: string; label: string; status: "pass" | "fail" | "pending" | "warn"; detail: string };
export type Readiness = {
  batch_id: number;
  readiness: string;
  readiness_reason: string | null;
  recovery_owner: string | null;
  checks: Check[];
  /** The 7-point readiness record (Module 15 §5); points 1 to 6 must pass before a proposal. */
  checklist: Check[];
  suggested: { readiness: string; readiness_reason: string | null; recovery_owner: string | null };
};
export type AllocationReview = {
  enrolment: { enrolment_id: number; enrolment_code: string };
  enrolment_track_id: number | null;
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
  enrolment_track_id: number | null;
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
  tracks?: { enrolment_track_id: number; track_code: string; track_name: string; role: string; curriculum_version: VersionRef | null }[];
  waiting_days?: number;
  /** Module 15 §6 allocation deadline (allocation queue only). */
  allocation_due_on?: DateOnly;
  open_batches?: (BatchRef & { capacity: number; state: string })[];
};

// ---------------------------------------------------------------- sessions

export type Join = { enabled: boolean; reason: string | null; url: string | null };
export type SessionPurpose = "Regular" | "Replacement" | "Remedial" | "Extra";
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
  /** What to show: Planned / Confirmed / Rescheduled / In Progress / Held / Partially Held / Cancelled. */
  state_label: string;
  delivered_at: DateTime | null;
  notes: string | null;
  original_starts_at: DateTime;
  original_ends_at: DateTime;
  confirmed_at: DateTime | null;
  /** When the trainer started the class. */
  live_at: DateTime | null;
  purpose: SessionPurpose;
  replaces_session_id: number | null;
  approval_status: "Not Required" | "Pending" | "Approved" | "Rejected";
  delivery_outcome: "Held" | "Partially Held" | null;
  actual_start: DateTime | null;
  actual_end: DateTime | null;
  break_minutes: number | null;
  planned_minutes: number | null;
  delivered_minutes: number | null;
  unfulfilled_note: string | null;
  hosting_branch_id: number | null;
  /** Staff only. */
  purpose_reference?: string | null;
  owner?: UserRef | null;
  due_on?: DateOnly | null;
  replacement_waiver?: string | null;
  room_override_reason?: string | null;
  log_overdue_at?: DateTime | null;
  meet_space_id?: string | null;
  calendar_event_id?: string | null;
  calendar_series_id?: string | null;
  conference_record_id?: string | null;
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
  emergency_reason?: string | null;
  next_action?: string | null;
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
  /** Topics Done of all topics of the course (db/109), and where to carry on. */
  topics: { done: number; total: number; percent: number | null } | null;
  continue_topic: {
    topic_id: number;
    title: string;
    title_te: string | null;
    module: { module_id: number; title: string; title_te: string | null };
    status: string;
  } | null;
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
  topics_done: number;
  percent: number | null;
};
export type TrackRow = {
  enrolment_track_id: number;
  track_code: string;
  track_name: string;
  role: string;
  curriculum_version: VersionRef | null;
  delivery: Delivery;
  topics: { done: number; total: number; percent: number | null } | null;
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
export type TopicProgress = {
  status: "Done" | "Work to hand in" | "Not started";
  is_done: boolean;
  attended: boolean;
  recording_watched: boolean;
  required_assignments: number;
  assignments_handed_in: number;
  required_tests: number;
  tests_taken: number;
};
export type ModulePage = ModuleHead & {
  context: Context;
  status: string | null;
  topics: (TopicRow & { session_count: number; progress: TopicProgress | null })[];
};
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

/** Everything a student has for one topic (GET /me/topics/{id}). */
export type TopicHub = {
  topic: { topic_id: number; title: string; title_te: string | null; outcome: string | null; is_required: boolean; instructional_minutes: number | null };
  module: { module_id: number; title: string; title_te: string | null };
  track: { track_code: string; track_name: string } | null;
  enrolment: { enrolment_id: number; enrolment_code: string; course: CourseRef };
  progress: TopicProgress | null;
  sessions: {
    session_id: number;
    session_code: string;
    title: string;
    starts_at: DateTime;
    ends_at: DateTime;
    state: string;
    state_label?: string;
    mode: string;
    trainer: string;
    attendance: string | null;
  }[];
  recordings: StudentRecording[];
  materials: StudentResource[];
  assignments: Assignment[];
  tests: TestItem[];
  next_topic: { topic_id: number; title: string; title_te: string | null } | null;
};

// ---------------------------------------------------------------- Module 15 / 16 records

export type Emergency = { emergency_reason?: string; next_action?: string };
export type MeetIds = {
  meet_space_id?: string | null;
  calendar_event_id?: string | null;
  calendar_series_id?: string | null;
  conference_record_id?: string | null;
};
export type ClassLog = {
  outcome?: "Held" | "Partially Held";
  actual_start?: string;
  actual_end?: string;
  break_minutes?: number;
  unfulfilled_note?: string;
  notes?: string;
};
export type DecisionStatus = "Pending" | "Approved" | "Rejected";
type DecisionFields = {
  status: string;
  requested_by: UserRef | null;
  requested_at: DateTime;
  decided_by: UserRef | null;
  decided_at: DateTime | null;
  decision_note: string | null;
};
export type CapacityRequest = DecisionFields & {
  request_id: number;
  batch: BatchRef;
  from_capacity: number;
  to_capacity: number;
  classroom_capacity: number | null;
  lab_capacity: number | null;
  online_capacity: number | null;
  resource_validation: string;
  academic_review: string;
};
export type TransferRequest = DecisionFields & {
  request_id: number;
  enrolment_id: number;
  enrolment: { enrolment_id: number; enrolment_code: string } | null;
  enrolment_track_id: number | null;
  from_batch: BatchRef | null;
  to_batch: BatchRef;
  from_branch_id: number | null;
  to_branch_id: number;
  interbranch: boolean;
  reason: string;
  acknowledged_warnings: string[] | null;
  destination_confirmed_by: UserRef | null;
  destination_confirmed_at: DateTime | null;
  applied_allocation_id: number | null;
};
export const CHANGE_KINDS = ["Start date", "Delivery mode", "Teaching days / times", "End date extension", "Instructional hours", "Batch move"] as const;
export type ChangeKind = (typeof CHANGE_KINDS)[number];
export type ChangeResponse = {
  response_id: number;
  enrolment_id: number;
  response: "Pending" | "Agreed" | "Declined";
  note: string | null;
  alternative_arranged: string | null;
  recorded_via: string | null;
  recorded_by: UserRef | null;
  responded_at: DateTime | null;
};
export type MaterialChange = DecisionFields & {
  change_id: number;
  batch: BatchRef;
  kind: ChangeKind;
  current_plan: string | null;
  proposed_plan: string;
  reason: string;
  changes: Record<string, unknown> | null;
  alternative: string | null;
  applied_at: DateTime | null;
  response_counts: Record<string, number>;
  responses?: ChangeResponse[];
};
export type MyMaterialChange = MaterialChange & { my_response: ChangeResponse };
export type Succession = DecisionFields & {
  succession_id: number;
  kind: "Merge" | "Split";
  from_batch: BatchRef;
  to_batch: BatchRef;
  enrolment_ids: number[] | null;
  effective_from: DateOnly;
  reason: string;
  academic_review: string;
  moved_count: number | null;
};
export type BatchSuccession = Succession;
export type BatchHandover = {
  handover_id: number;
  batch_id: number;
  enrolment_id: number;
  owner: UserRef | null;
  plan: string;
  destination: string;
  destination_batch_id: number | null;
  recorded_at: DateTime;
};
export type SlotOption = {
  batch_id: number;
  batch_code: string;
  display_name: string | null;
  mode: string;
  schedule_pattern: string;
  planned_start: DateOnly | null;
  schedule_days: string[];
  start_time: string | null;
  end_time: string | null;
  state_label: string;
  is_full: boolean;
};
export type SlotStatus = "Requested" | "Waitlisted" | "Confirmed" | "Not Possible" | "Withdrawn";
export type SlotPreference = {
  preference_id: number;
  enrolment_id: number;
  enrolment: { enrolment_id: number; enrolment_code: string } | null;
  batch: BatchRef | null;
  preferred_days: string[];
  preferred_start: string | null;
  preferred_end: string | null;
  preferred_mode: string | null;
  note: string | null;
  status: SlotStatus;
  status_note: string | null;
  status_at: DateTime | null;
  created_at: DateTime;
  reserves_seat: false;
};

type SessionRef = {
  session_id: number;
  session_code: string;
  title: string;
  starts_at: DateTime;
  ends_at: DateTime;
  state: string;
  state_label: string;
};
export type SessionRefWithBatch = SessionRef & { batch: BatchRef; branch_id?: number };
export type SessionPerson = {
  session_person_id: number;
  session_id: number;
  role: "Host" | "Backup" | "Guest";
  user: UserRef | null;
  guest_name: string | null;
  guest_email: string | null;
  purpose: string | null;
  student_agreement: string | null;
  status: string;
  added_by: UserRef | null;
  added_at: DateTime;
  decided_by: UserRef | null;
  decided_at: DateTime | null;
  removed_at: DateTime | null;
};
export type MeetIncident = {
  incident_id: number;
  session_id: number;
  kind: string;
  description: string;
  actions_taken: string;
  old_meet_link: string | null;
  link_replaced: boolean;
  reported_by: UserRef | null;
  reported_at: DateTime;
  participants_notified_at: DateTime | null;
  manager_alerted_at: DateTime | null;
};
export type Participation = {
  participation_id: number;
  session_id: number;
  participant_name: string | null;
  participant_email: string | null;
  joined_at: DateTime;
  left_at: DateTime | null;
  source: string;
  match_status: "Matched" | "Unmatched" | "Dismissed";
  matched_user: UserRef | null;
  matched_enrolment_id: number | null;
  reviewed_at: DateTime | null;
  review_note: string | null;
};
export type Disruption = {
  disruption_id: number;
  session: SessionRefWithBatch;
  kind: string;
  cause: string;
  detected_at: DateTime;
  delay_minutes: number | null;
  detail: string | null;
  undelivered_minutes: number | null;
  recovery_plan: string | null;
  replacement_session_id: number | null;
  owner: UserRef | null;
  status: "Open" | "Resolved";
  raised_by_job: boolean;
  resolved_by: UserRef | null;
  resolved_at: DateTime | null;
};
export type CoverRequest = {
  request_id: number;
  session: SessionRefWithBatch;
  cover_role: "Substitute" | "Assistant";
  planned_trainer: UserRef | null;
  cover: UserRef | null;
  reason: string;
  scope: string;
  handover: string;
  status: "Pending" | "Approved" | "Applied" | "Rejected";
  requested_by: UserRef | null;
  requested_at: DateTime;
  approved_by: UserRef | null;
  approved_at: DateTime | null;
  verified_by: UserRef | null;
  verified_at: DateTime | null;
  verification_note: string | null;
  decision_note: string | null;
  applied_at: DateTime | null;
};
export type SessionRoster = {
  session_id: number;
  batch: BatchRef;
  branch_id: number;
  topic_id: number | null;
  coverage_note: string;
  verified_by: UserRef | null;
  verified_at: DateTime | null;
};
export type SessionOperations = {
  people: SessionPerson[];
  incidents: MeetIncident[];
  disruptions: Disruption[];
  cover_requests: CoverRequest[];
  rosters: SessionRoster[];
  participation: Participation[];
  replacements: SessionRef[];
};
export type JobRunRow = {
  job_name: string;
  last_started_at: DateTime | null;
  last_finished_at?: DateTime | null;
  last_ok_at: DateTime | null;
  last_result?: unknown;
  last_error?: string | null;
};
export type MeetOpsRow = SessionRef & {
  batch: BatchRef;
  branch: BranchRef;
  mode: string;
  trainer: UserRef;
  purpose: SessionPurpose;
  meet_status_label: string | null;
  link_ready: boolean | null;
  host: string | null;
  backup: string | null;
  host_ready: boolean | null;
  delay_notice_at: DateTime | null;
  disruption: Disruption | null;
  attendance: { seats: number; marked: number; awaiting_confirmation: boolean };
  recording: string[];
  log_overdue: boolean;
};
export type MeetOperations = {
  date: DateOnly;
  sessions: MeetOpsRow[];
  summary: { classes: number; online_not_ready: number; delayed_or_disrupted: number; attendance_awaiting: number };
  open_disruptions: Disruption[];
  replacements_owed: SessionRefWithBatch[];
  awaiting_approval: (SessionRefWithBatch & { purpose: SessionPurpose })[];
  missing_logs: (SessionRefWithBatch & { trainer: string })[];
  open_recording_issues: number;
  unmatched_participants: number;
  integration: { note: string; verified: boolean };
  last_runs: JobRunRow[];
};

const opsCalls = {
  // capacity
  requestCapacity: (batchId: number, body: Record<string, unknown>) => post<CapacityRequest>(`/batches/${batchId}/capacity-requests`, body),
  capacityRequests: (query: Query = {}) => list<CapacityRequest>("/batch-capacity-requests", { per_page: 100, ...query }),
  decideCapacity: (id: number, body: { decision: "Approved" | "Rejected"; note?: string }) =>
    post<CapacityRequest>(`/batch-capacity-requests/${id}/decision`, body),
  // transfers
  requestTransfer: (enrolmentId: number, body: { to_batch_id: number; enrolment_track_id?: number | null; reason: string; acknowledge_warnings?: boolean }) =>
    post<TransferRequest>(`/enrolments/${enrolmentId}/transfer-requests`, body),
  transferRequests: (query: Query = {}) => list<TransferRequest>("/batch-transfer-requests", { per_page: 100, ...query }),
  confirmDestination: (id: number, body: { decision: "Confirmed" | "Rejected"; note?: string }) =>
    post<TransferRequest>(`/batch-transfer-requests/${id}/destination`, body),
  decideTransfer: (id: number, body: { decision: "Approved" | "Rejected"; note?: string }) =>
    post<TransferRequest>(`/batch-transfer-requests/${id}/decision`, body),
  // material changes
  proposeChange: (batchId: number, body: Record<string, unknown>) => post<MaterialChange>(`/batches/${batchId}/material-changes`, body),
  changes: (query: Query = {}) => list<MaterialChange>("/material-changes", { per_page: 100, ...query }),
  change: (id: number) => get<MaterialChange>(`/material-changes/${id}`),
  decideChange: (id: number, body: { decision: "Approved" | "Rejected"; note?: string }) => post<MaterialChange>(`/material-changes/${id}/decision`, body),
  recordChangeResponse: (id: number, body: { enrolment_id: number; response: "Agreed" | "Declined"; note: string; alternative_arranged?: string }) =>
    post<MaterialChange>(`/material-changes/${id}/responses`, body),
  applyChange: (id: number) => post<MaterialChange>(`/material-changes/${id}/apply`),
  withdrawChange: (id: number, note: string) => post<MaterialChange>(`/material-changes/${id}/withdraw`, { note }),
  myChanges: () => get<MyMaterialChange[]>("/me/material-changes"),
  respondToChange: (id: number, body: { response: "Agreed" | "Declined"; note?: string }) => post<MaterialChange>(`/me/material-changes/${id}/response`, body),
  // merge / split
  successions: (query: Query = {}) => list<Succession>("/batch-successions", { per_page: 100, ...query }),
  requestSuccession: (body: Record<string, unknown>) => post<Succession>("/batch-successions", body),
  decideSuccession: (id: number, body: { decision: "Approved" | "Rejected"; note?: string }) => post<Succession>(`/batch-successions/${id}/decision`, body),
  // slot preferences
  slotOptions: (enrolmentId: number) => get<SlotOption[]>("/me/slot-options", { enrolment_id: enrolmentId }),
  mySlotPreferences: () => get<SlotPreference[]>("/me/slot-preferences"),
  requestSlot: (body: Record<string, unknown>) => post<SlotPreference>("/me/slot-preferences", body),
  withdrawSlot: (id: number) => post<SlotPreference>(`/me/slot-preferences/${id}/withdraw`),
  slotPreferences: (query: Query = {}) => list<SlotPreference>("/slot-preferences", { per_page: 100, ...query }),
  setSlotStatus: (id: number, body: { status: string; status_note?: string; batch_id?: number | null }) =>
    patch<SlotPreference>(`/slot-preferences/${id}`, body),
  // Meet operations
  meetOperations: (query: Query = {}) => get<MeetOperations>("/meet-operations", query),
  sessionOperations: (id: number) => get<SessionOperations>(`/class-sessions/${id}/operations`),
  addPerson: (id: number, body: Record<string, unknown>) => post<SessionPerson>(`/class-sessions/${id}/people`, body),
  decideGuest: (personId: number, body: { decision: "Approved" | "Rejected"; note?: string }) =>
    post<SessionPerson>(`/session-people/${personId}/decision`, body),
  removePerson: (personId: number) => del<SessionPerson>(`/session-people/${personId}`),
  reportIncident: (id: number, body: { kind: string; description: string; actions_taken: string; replace_link?: boolean }) =>
    post<MeetIncident>(`/class-sessions/${id}/meet-incidents`, body),
  recordParticipation: (
    id: number,
    body: { source?: string; entries: { participant_name?: string; participant_email?: string; joined_at: string; left_at?: string }[] },
  ) => post<Participation[]>(`/class-sessions/${id}/participation`, body),
  unmatched: (query: Query = {}) => list<Participation>("/meet-participation/unmatched", { per_page: 100, ...query }),
  reviewParticipation: (id: number, body: { match_status: "Matched" | "Dismissed"; user_id?: number | null; note?: string }) =>
    post<Participation>(`/meet-participation/${id}/review`, body),
  recordDisruption: (id: number, body: { kind: string; cause?: string; delay_minutes?: number | null; detail?: string }) =>
    post<Disruption>(`/class-sessions/${id}/disruptions`, body),
  resolveDisruption: (
    id: number,
    body: { recovery_plan: string; undelivered_minutes: number; cause?: string; replacement_session_id?: number | null; owner_user_id?: number | null },
  ) => post<Disruption>(`/session-disruptions/${id}/resolve`, body),
  requestCover: (id: number, body: { cover_role: string; cover_user_id: number; reason: string; scope: string; handover: string }) =>
    post<CoverRequest>(`/class-sessions/${id}/cover-requests`, body),
  decideCover: (id: number, body: { decision: "Approved" | "Rejected"; note?: string }) => post<CoverRequest>(`/session-cover-requests/${id}/decision`, body),
  verifyCover: (id: number, note: string) => post<CoverRequest>(`/session-cover-requests/${id}/verification`, { note }),
  addRoster: (id: number, body: { batch_id: number; topic_id?: number | null; coverage_note: string }) =>
    post<SessionRoster>(`/class-sessions/${id}/rosters`, body),
  removeRoster: (id: number, batchId: number) => del<unknown>(`/class-sessions/${id}/rosters/${batchId}`),
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
  addTopic: (moduleId: number, body: { title: string; is_required?: boolean; topic_class?: TopicClass }) =>
    post<TopicRow>(`/curriculum-modules/${moduleId}/topics`, body),
  updateTopic: (id: number, body: Record<string, unknown>) => patch<TopicRow>(`/curriculum-topics/${id}`, body),
  verifyHours: (id: number) => post<CurriculumVersion>(`/curriculum-versions/${id}/hours-verification`),
  setCompletionProfile: (id: number, body: CompletionProfile) => put<CurriculumVersion>(`/curriculum-versions/${id}/completion-profile`, body),
  addRequirement: (id: number, body: Record<string, unknown>) => post<AssessmentRequirement>(`/curriculum-versions/${id}/assessment-requirements`, body),
  deleteRequirement: (id: number) => del<null>(`/assessment-requirements/${id}`),
  pinComponent: (id: number, body: { component_id: number; component_version_id: number }) =>
    put<CurriculumVersion>(`/curriculum-versions/${id}/components`, body),
  reviewEquivalence: (componentId: number, note: string) => post<Component>(`/course-components/${componentId}/equivalence`, { note }),
  // Module 14 records
  mappings: (query: Query) => list<AcademicMapping>("/academic-mappings", { per_page: 100, ...query }),
  requestMapping: (enrolmentId: number, body: Record<string, unknown>) => post<AcademicMapping>(`/enrolments/${enrolmentId}/academic-mappings`, body),
  decideMapping: (id: number, body: { decision: string; note?: string; student_acceptance?: string }) =>
    post<AcademicMapping>(`/academic-mappings/${id}/decision`, body),
  rules: (query: Query) => list<EquivalenceRule>("/equivalence-rules", { per_page: 100, ...query }),
  requestRule: (body: { from_version_id: number; to_version_id: number; description: string }) => post<EquivalenceRule>("/equivalence-rules", body),
  decideRule: (id: number, body: { decision: string; note?: string }) => post<EquivalenceRule>(`/equivalence-rules/${id}/decision`, body),
  variations: (query: Query) => list<CurriculumVariation>("/curriculum-variations", { per_page: 100, ...query }),
  createVariation: (body: Record<string, unknown>) => post<CurriculumVariation>("/curriculum-variations", body),
  decideVariation: (id: number, body: { decision: string; note?: string }) => post<CurriculumVariation>(`/curriculum-variations/${id}/decision`, body),
  library: () => list<LibraryModule>("/curriculum-library", { per_page: 100 }),
  saveToLibrary: (moduleId: number) => post<LibraryModule>(`/curriculum-modules/${moduleId}/library`),
  proposeLibraryVersion: (libraryModuleId: number, body: { module_id: number; change_note: string }) =>
    post<LibraryVersion>(`/curriculum-library/${libraryModuleId}/versions`, body),
  decideLibraryVersion: (id: number, decision: string) => post<LibraryVersion>(`/curriculum-library-versions/${id}/decision`, { decision }),
  insertLibraryModule: (versionId: number, libraryVersionId: number) =>
    post<ModuleContent>(`/curriculum-versions/${versionId}/library-modules`, { library_version_id: libraryVersionId }),
  deleteTopic: (id: number) => del<null>(`/curriculum-topics/${id}`),

  // batches
  batches: (query: Query) => list<Batch>("/batches", { per_page: 100, ...query }),
  batch: (id: number) => get<BatchDetail>(`/batches/${id}`),
  createBatch: (body: Record<string, unknown>) => post<Batch>("/batches", body),
  updateBatch: (id: number, body: Record<string, unknown>) => patch<Batch>(`/batches/${id}`, body),
  batchState: (id: number, body: { state: "Running" | "On Hold" | "Resume" | "Completed" | "Cancelled" | "Archived"; reason?: string }) =>
    post<Batch>(`/batches/${id}/state`, body),
  proposeBatch: (id: number, note?: string) => post<Batch>(`/batches/${id}/proposal`, { note }),
  decideConfirmation: (id: number, body: { decision: "Confirmed" | "Returned"; note?: string; override_reason?: string }) =>
    post<Batch>(`/batches/${id}/confirmation`, body),
  recordHandover: (
    id: number,
    body: { enrolment_id: number; owner_user_id: number; plan: string; destination: string; destination_batch_id?: number | null },
  ) => post<BatchHandover>(`/batches/${id}/handovers`, body),
  readiness: (id: number) => get<Readiness>(`/batches/${id}/readiness`),
  setReadiness: (id: number, body: { readiness: string; readiness_reason?: string | null; recovery_owner?: string | null }) =>
    patch<Readiness>(`/batches/${id}/readiness`, body),
  assignTrainer: (id: number, body: { trainer_user_id: number; role: string }) => post<Trainer>(`/batches/${id}/trainers`, body),
  trainerRole: (id: number, assignmentId: number, role: string) => patch<Trainer>(`/batches/${id}/trainers/${assignmentId}`, { role }),
  endTrainer: (id: number, assignmentId: number) => del<Trainer>(`/batches/${id}/trainers/${assignmentId}`),
  roster: (id: number, query: Query = {}) => list<RosterRow>(`/batches/${id}/allocations`, { per_page: 100, ...query }),
  review: (batchId: number, enrolmentId: number, options: { transfer?: boolean; enrolment_track_id?: number | null } = {}) =>
    get<AllocationReview>(`/batches/${batchId}/allocation-review`, {
      enrolment_id: enrolmentId,
      transfer: options.transfer ?? false,
      enrolment_track_id: options.enrolment_track_id ?? undefined,
    }),
  allocate: (batchId: number, body: { enrolment_id: number; enrolment_track_id?: number | null; reason?: string; acknowledge_warnings?: boolean }) =>
    post<Allocation>(`/batches/${batchId}/allocations`, body),
  deallocate: (enrolmentId: number, reason: string, enrolment_track_id?: number | null) =>
    post<Allocation>(`/enrolments/${enrolmentId}/deallocate`, { reason, enrolment_track_id }),
  enrolments: (query: Query) => list<EnrolmentRow>("/enrolments", { per_page: 100, ...query }),
  allocationQueue: (query: Query = {}) => list<EnrolmentRow>("/allocation-queue", { per_page: 100, ...query }),
  staff: (role: string, branchId: number) => get<{ user_id: number; full_name: string }[]>("/reference/staff", { role, branch_id: branchId }),
  courses: () => get<(CourseRef & { is_combo: boolean })[]>("/reference/courses"),

  // sessions
  sessions: (query: Query) => list<ClassSession>("/class-sessions", { per_page: 100, ...query }),
  session: (id: number) => get<SessionDetail>(`/class-sessions/${id}`),
  createSessions: (body: Record<string, unknown>) => post<ClassSession[]>("/class-sessions", body),
  updateSession: (id: number, body: Record<string, unknown>) => patch<ClassSession>(`/class-sessions/${id}`, body),
  reschedule: (id: number, body: { starts_at: string; ends_at: string; reason: string; override_reason?: string } & Emergency) =>
    post<ClassSession>(`/class-sessions/${id}/reschedule`, body),
  cancelSession: (id: number, body: { reason: string } & Emergency) => post<ClassSession>(`/class-sessions/${id}/cancel`, body),
  startSession: (id: number) => post<ClassSession>(`/class-sessions/${id}/start`),
  deliverSession: (id: number, body: ClassLog = {}) => post<ClassSession>(`/class-sessions/${id}/deliver`, body),
  confirmSession: (id: number) => post<ClassSession>(`/class-sessions/${id}/confirm`),
  decidePurpose: (id: number, body: { decision: "Approved" | "Rejected"; note?: string }) => post<ClassSession>(`/class-sessions/${id}/approval`, body),
  waiveReplacement: (id: number, reason: string) => post<ClassSession>(`/class-sessions/${id}/replacement-waiver`, { reason }),
  meetLink: (id: number, meet_link: string, ids: MeetIds = {}) => put<ClassSession>(`/class-sessions/${id}/meet`, { meet_link, ...ids }),
  meetFailed: (id: number, detail: string) => post<ClassSession>(`/class-sessions/${id}/meet/fail`, { detail }),
  meetReset: (id: number) => post<ClassSession>(`/class-sessions/${id}/meet/reset`),
  requests: (query: Query) => list<RescheduleRequest>("/reschedule-requests", { per_page: 100, ...query }),
  requestReschedule: (id: number, body: { proposed_starts_at: string; proposed_ends_at: string; reason: string }) =>
    post<RescheduleRequest>(`/class-sessions/${id}/reschedule-requests`, body),
  approveRequest: (id: number, body: { note?: string; override_reason?: string } & Emergency = {}) =>
    post<RescheduleRequest>(`/reschedule-requests/${id}/approve`, body),
  rejectRequest: (id: number, note: string) => post<RescheduleRequest>(`/reschedule-requests/${id}/reject`, { note }),

  // Module 15 / 16 operations
  ...opsCalls,

  // learner
  myEnrolments: () => get<MyEnrolment[]>("/me/enrolments"),
  myEnrolment: (id: number) => get<MyEnrolmentDetail>(`/me/enrolments/${id}`),
  myTrack: (id: number, trackId: number) => get<TrackDetail>(`/me/enrolments/${id}/tracks/${trackId}`),
  mySchedule: (query: Query) => list<ClassSession>("/me/schedule", { per_page: 100, ...query }),
  module: (id: number) => get<ModulePage>(`/modules/${id}`),
  topic: (id: number) => get<TopicPage>(`/topics/${id}`),
  topicHub: (id: number) => get<TopicHub>(`/me/topics/${id}`),
};
