/** Assessments API (slice S3): assignments, submissions, question bank, tests, attempts, mock interviews, results. */
import { download, get, list, post, patch, put, upload, type Page } from "./client";
import type { DateTime } from "./types";

type Ref = { batch_id: number; batch_code: string; course_code: string };

// ---------------------------------------------------------------- assignments

export type AssignmentState = "Upcoming" | "Due" | "Overdue" | "Submitted" | "Under Review" | "Reviewed" | "Resubmission Requested";

export type Review = {
  review_id?: number;
  outcome: "Reviewed" | "Resubmission Requested";
  feedback: string | null;
  marks: string | null;
  resubmission_due_at: DateTime | null;
  reviewed_at?: DateTime;
  reviewer?: { user_id: number; full_name: string };
};

export type Submission = {
  submission_id: number;
  submission_code: string;
  assignment: { assignment_id: number; assignment_code: string; title: string } & Partial<Assignment>;
  student: { student_id: number; student_code: string; full_name: string };
  enrolment_id: number;
  version_no: number;
  attempt_no: number;
  body_text: string | null;
  link_url: string | null;
  file: { filename: string; mime_type: string | null; size_bytes: number } | null;
  ai_disclosure: string | null;
  submitted_at: DateTime;
  is_late: boolean;
  review_started_at: DateTime | null;
  review: Review | null;
  versions?: Submission[];
};

export type SubmissionWindow = { allowed: boolean; mode: "initial" | "replacement" | "resubmission" | null; reason: string | null; deadline: DateTime | null };

export type Assignment = {
  assignment_id: number;
  assignment_code: string;
  title: string;
  batch: Ref;
  module: { module_id: number; title: string } | null;
  topic: { topic_id: number; title: string } | null;
  kind: string;
  brief: string;
  attachments: { name: string; url: string }[];
  is_required: boolean;
  max_marks: string;
  release_at: DateTime;
  due_at: DateTime;
  closes_at: DateTime;
  max_resubmissions: number;
  late_policy: string;
  ai_use_rule: string;
  reviewer: { user_id: number; full_name: string };
  status: "Draft" | "Released" | "Withdrawn";
  withdrawn_reason: string | null;
  counts?: { submitted: number; awaiting_review: number; reviewed: number; resubmission_requested: number };
  can_manage?: boolean;
  my?: {
    enrolment_id: number;
    state: AssignmentState;
    versions: Submission[];
    window: SubmissionWindow;
    is_late: boolean;
    result: { status: string | null; marks: string | null; max_marks: string };
  };
};

export type AssignmentInput = {
  batch_id: number;
  topic_id?: number | null;
  title: string;
  kind: string;
  brief: string;
  is_required: boolean;
  max_marks: number;
  due_at: string;
  ai_use_rule: string;
  attachments?: { name: string; url: string }[];
  release_now?: boolean;
};

export type CurriculumOption = { module_id: number; title: string; version_label: string; topics: { topic_id: number; title: string }[] };

export const ASSIGNMENT_KINDS = ["Class assignment", "Module assignment", "Practical lab", "Mini project", "Final project"] as const;
export const AI_RULES = ["Allowed with disclosure", "Limited to specified uses", "Not permitted"] as const;

// ---------------------------------------------------------------- question bank

export const QUESTION_TYPES = [
  "Single choice",
  "Multiple choice",
  "True / False",
  "Numeric",
  "Short answer",
  "Descriptive",
  "Coding",
  "Output prediction",
] as const;
export type QuestionType = (typeof QUESTION_TYPES)[number];

export type Question = {
  question_id: number;
  question_code: string;
  course: { course_id: number; course_code: string; title: string };
  branch: { branch_id: number; branch_code: string };
  topic: { topic_id: number; title: string } | null;
  question_type: QuestionType;
  stem: string;
  options: { key: string; text: string }[];
  answer_key: Record<string, unknown>;
  explanation: string | null;
  marks: string;
  difficulty: "Easy" | "Medium" | "Hard";
  tags: string[];
  status: "Draft" | "Approved" | "Retired";
  version: number;
  author: { user_id: number; full_name: string };
};

export type QuestionInput = {
  course_id: number;
  topic_id?: number | null;
  question_type: QuestionType;
  stem: string;
  options: { key: string; text: string }[];
  answer_key: Record<string, unknown>;
  marks: number;
  difficulty: string;
  tags: string[];
};

// ---------------------------------------------------------------- tests

export const TEST_KINDS = ["Practice quiz", "Module test", "Coding exercise", "Mock test", "Mock interview", "Final test"] as const;

export type SlotStatus = "Open" | "Slot Confirmation Pending" | "Confirmed" | "Completed" | "Cancelled";

export type Slot = {
  slot_id: number;
  test: { test_id: number; test_code: string; title: string };
  trainer: { user_id: number; full_name: string };
  starts_at: DateTime;
  ends_at: DateTime;
  status: SlotStatus;
  student: { student_id: number; student_code: string; full_name: string } | null;
  rating: number | null;
  strengths: string | null;
  improvements: string | null;
  next_action: string | null;
};

export type AttemptSummary = {
  attempt_id: number;
  attempt_no: number;
  status: "In Progress" | "Submitted";
  grading_status: "Pending" | "Awaiting Grading" | "Graded";
  started_at: DateTime;
  submitted_at: DateTime | null;
  receipt_code: string | null;
  score?: string | null;
};

export type TestQuestion = {
  question_id: number;
  position: number;
  question_type: QuestionType;
  stem: string;
  options: { key: string; text: string }[];
  marks: string;
  question_version?: number;
  answer_key?: Record<string, unknown>;
};

export type TestItem = {
  test_id: number;
  test_code: string;
  title: string;
  kind: (typeof TEST_KINDS)[number];
  batch: Ref;
  module: { module_id: number; title: string } | null;
  topic: { topic_id: number; title: string } | null;
  instructions: string | null;
  is_required: boolean;
  is_formal: boolean;
  ai_use_rule: string;
  duration_minutes: number | null;
  opens_at: DateTime | null;
  closes_at: DateTime | null;
  attempts_allowed: number | null;
  pass_marks: string | null;
  release_status: "Configuration Pending" | "Not Released" | "Released" | "Closed";
  status: "Configuration Pending" | "Not Released" | "Scheduled" | "Available" | "Closed";
  approved_at: DateTime | null;
  question_count: number;
  total_marks?: string;
  gaps?: string[];
  attempt_count?: number;
  slot_count?: number;
  can_manage?: boolean;
  can_moderate?: boolean;
  questions?: TestQuestion[];
  my?: {
    enrolment_id: number;
    my_status: string | null;
    attempts_used: number;
    attempts_remaining: number | null;
    in_progress_attempt_id: number | null;
    latest_attempt: AttemptSummary | null;
    slot: Slot | null;
    can_start: boolean;
  };
};

export type TestInput = {
  batch_id: number;
  kind: string;
  title: string;
  topic_id?: number | null;
  instructions?: string;
  duration_minutes?: number | null;
  opens_at?: string | null;
  closes_at?: string | null;
  attempts_allowed?: number | null;
  pass_marks?: number | null;
};

export type StudentAttempt = {
  attempt: AttemptSummary & { deadline_at: DateTime | null; submit_reason: string | null; remaining_seconds: number | null; total_marks: string };
  test: {
    test_id: number;
    test_code: string;
    title: string;
    kind: string;
    duration_minutes: number | null;
    instructions: string | null;
    ai_use_rule: string;
    is_formal: boolean;
  };
  questions: TestQuestion[];
  answers: Record<string, unknown>;
  server_time: DateTime;
};

export type SaveResult = { accepted: boolean; status: string; receipt_code: string | null; remaining_seconds: number | null; saved_at: DateTime | null };

export type StaffAttempt = {
  attempt: AttemptSummary & { auto_score: string | null; total_score: string | null; total_marks: string };
  student: { student_id: number; student_code: string; full_name: string };
  test: { test_id: number; test_code: string; title: string; kind: string };
  questions: (TestQuestion & {
    answer: unknown;
    awarded_marks: string | null;
    is_auto_graded: boolean;
    grader_feedback: string | null;
    needs_grading: boolean;
  })[];
  can_grade: boolean;
};

export type AttemptRow = AttemptSummary & {
  student: { student_id: number; student_code: string; full_name: string };
  test: { test_id: number; test_code: string; title: string; kind: string };
  batch: Ref;
  auto_score: string | null;
  total_score: string | null;
  total_marks: string;
  manual_pending: number;
};

// ---------------------------------------------------------------- results

export type MyResult = {
  key: string;
  kind: "Assignment" | "Test";
  item_id: number;
  item: string;
  type: string;
  score: string | null;
  state: string;
  pass_status: string | null;
  published_at: DateTime | null;
};

export type Result = {
  result_id: number;
  student: { student_id: number; student_code: string; full_name: string };
  batch: Ref;
  item: { kind: "Assignment" | "Test"; item_id: number; code: string; title: string; type: string };
  max_marks: string;
  provisional_marks: string;
  moderated_marks: string | null;
  final_marks: string | null;
  status: "Provisional" | "Moderated" | "Published";
  moderation_reason: string | null;
};

export type ReviewQueueRow = {
  kind: "Assignment" | "Test";
  item_id: number;
  code: string;
  title: string;
  type: string;
  batch: Ref;
  counts: { provisional: number; moderated: number; published: number; awaiting_grading: number };
  state: string;
  gaps?: string[];
  can_moderate: boolean;
};

// ---------------------------------------------------------------- calls

type Filters = Record<string, string | number | boolean | undefined>;

export const assessmentsApi = {
  // assignments
  assignments: (query?: Filters): Promise<Page<Assignment>> => list("/assignments", { per_page: 100, ...query }),
  assignment: (id: number) => get<Assignment>(`/assignments/${id}`),
  curriculum: (batchId: number) => get<CurriculumOption[]>("/assessments/curriculum", { batch_id: batchId }),
  createAssignment: (body: AssignmentInput) => post<Assignment>("/assignments", body),
  updateAssignment: (id: number, body: Partial<AssignmentInput> & { reason?: string }) => patch<Assignment>(`/assignments/${id}`, body),
  releaseAssignment: (id: number) => post<Assignment>(`/assignments/${id}/release`, {}),
  withdrawAssignment: (id: number, reason: string) => post<Assignment>(`/assignments/${id}/withdraw`, { reason }),
  submit: (id: number, body: { body_text?: string; link_url?: string; ai_disclosure?: string }, file?: File | null) => {
    if (!file) return post<Submission>(`/assignments/${id}/submissions`, body);
    const form = new FormData();
    for (const [key, value] of Object.entries(body)) if (value) form.append(key, value);
    form.append("file", file);
    return upload<Submission>(`/assignments/${id}/submissions`, form);
  },
  submissions: (query?: Filters): Promise<Page<Submission>> => list("/submissions", { per_page: 100, ...query }),
  submission: (id: number) => get<Submission>(`/submissions/${id}`),
  startReview: (id: number) => post<Submission>(`/submissions/${id}/start-review`, {}),
  review: (id: number, body: { outcome: string; feedback: string; marks?: number; resubmission_due_at?: string }) =>
    post<Submission>(`/submissions/${id}/review`, body),
  downloadSubmission: (id: number, filename: string) => download(`/submissions/${id}/file`, undefined, filename),

  // question bank
  questions: (query?: Filters): Promise<Page<Question>> => list("/questions", { per_page: 100, ...query }),
  createQuestion: (body: QuestionInput) => post<Question>("/questions", body),
  approveQuestion: (id: number) => post<Question>(`/questions/${id}/approve`, {}),
  retireQuestion: (id: number) => post<Question>(`/questions/${id}/retire`, {}),
  newVersion: (id: number) => post<Question>(`/questions/${id}/new-version`, {}),

  // tests
  tests: (query?: Filters): Promise<Page<TestItem>> => list("/tests", { per_page: 100, ...query }),
  test: (id: number) => get<TestItem>(`/tests/${id}`),
  createTest: (body: TestInput) => post<TestItem>("/tests", body),
  updateTest: (id: number, body: Partial<TestInput>) => patch<TestItem>(`/tests/${id}`, body),
  setQuestions: (id: number, questionIds: number[]) =>
    put<TestItem>(`/tests/${id}/questions`, { questions: questionIds.map((question_id) => ({ question_id })) }),
  approveTest: (id: number) => post<TestItem>(`/tests/${id}/approve`, {}),
  releaseTest: (id: number, opensAt?: string) => post<TestItem>(`/tests/${id}/release`, opensAt ? { opens_at: opensAt } : {}),
  closeTest: (id: number) => post<TestItem>(`/tests/${id}/close`, {}),

  // attempts
  startAttempt: (testId: number) => post<StudentAttempt>(`/tests/${testId}/attempts`, {}),
  attempt: (id: number) => get<StudentAttempt>(`/attempts/${id}`),
  staffAttempt: (id: number) => get<StaffAttempt>(`/attempts/${id}`),
  saveAnswers: (id: number, answers: Record<string, unknown>) => put<SaveResult>(`/attempts/${id}/answers`, { answers }),
  submitAttempt: (id: number, answers?: Record<string, unknown>) => post<StudentAttempt>(`/attempts/${id}/submit`, answers ? { answers } : {}),
  attempts: (query?: Filters): Promise<Page<AttemptRow>> => list("/attempts", { per_page: 100, ...query }),
  grade: (id: number, grades: { question_id: number; marks: number; feedback?: string }[]) => post<StaffAttempt>(`/attempts/${id}/grade`, { grades }),

  // mock interviews
  slots: (testId: number) => get<Slot[]>(`/tests/${testId}/slots`),
  offerSlots: (testId: number, slots: { starts_at: string; ends_at: string }[]) => post<Slot[]>(`/tests/${testId}/slots`, { slots }),
  bookSlot: (id: number) => post<Slot>(`/interview-slots/${id}/book`, {}),
  confirmSlot: (id: number) => post<Slot>(`/interview-slots/${id}/confirm`, {}),
  cancelSlot: (id: number, reason?: string) => post<Slot>(`/interview-slots/${id}/cancel`, { reason }),
  completeSlot: (id: number, body: { rating: number; strengths: string; improvements: string; next_action: string }) =>
    post<Slot>(`/interview-slots/${id}/complete`, body),

  // results
  myResults: () => get<MyResult[]>("/me/results"),
  results: (query?: Filters): Promise<Page<Result>> => list("/results", { per_page: 100, ...query }),
  reviewQueue: (query?: Filters) => get<ReviewQueueRow[]>("/assessment-reviews", query),
  moderate: (id: number, marks: number, reason: string) => post<Result>(`/results/${id}/moderate`, { marks, reason }),
  publish: (body: { result_ids?: number[]; assignment_id?: number; test_id?: number }) => post<{ published: number }>("/results/publish", body),
};

/** Batches a staff member can author for (reads the Phase 1 /batches endpoint). */
export const batchesForAuthoring = (): Promise<Page<{ batch_id: number; batch_code: string; course: { course_id: number; title: string }; state: string }>> =>
  list("/batches", { per_page: 100 });
