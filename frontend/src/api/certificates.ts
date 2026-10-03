/** Completion review and the LMS Certificate Register (docs/API.md §4.7). */
import { useQuery } from "@tanstack/react-query";
import { get, list, post, type Query } from "./client";
import type { DateOnly, DateTime, UserRef } from "./types";
import type { Measures } from "./attendance";

export const CERTIFICATE_TYPES = ["Course Completion Certificate", "Internship Certificate"] as const;
export const CERTIFICATE_STATUSES = [
  "Not Yet Eligible",
  "Eligibility Review",
  "Awaiting Approval",
  "Approved for Issue",
  "Issued",
  "Superseded",
  "Revoked",
] as const;
export const COMPLETION_DECISIONS = ["Complete", "Not Yet", "Needs Recovery"] as const;
export type CompletionDecision = (typeof COMPLETION_DECISIONS)[number];
export type CertificateAction =
  | "recommend"
  | "approve"
  | "return"
  | "issue"
  | "request_correction"
  | "request_revocation"
  | "request_reinstatement";
export type RequestKind = "Correction" | "Revocation" | "Reinstatement";
export type ApprovalStatus = "Pending" | "Approved" | "Rejected";

type Ref = { student_id: number; student_code: string; full_name: string };
type EnrolmentRef = {
  enrolment_id: number;
  enrolment_code: string;
  course: { course_id: number; course_code: string; title: string };
  kind: string;
  status: string;
};

export type Certificate = {
  certificate_id: number;
  certificate_number: string | null;
  certificate_type: (typeof CERTIFICATE_TYPES)[number];
  version: number;
  version_label: string;
  status: (typeof CERTIFICATE_STATUSES)[number];
  enrolment: EnrolmentRef;
  student: Ref;
  course: { course_id: number; course_code: string; title: string };
  branch: { branch_id: number; branch_code: string; branch_name: string };
  holder_name: string;
  issue_date: DateOnly | null;
  reason: string | null;
  recommended_at: DateTime | null;
  approved_at: DateTime | null;
  revoked_at: DateTime | null;
  supersedes_certificate_id: number | null;
  actions: CertificateAction[];
  /** Module 22 §5: a paid admission's fee is cleared before the certificate goes ahead (staff views only). */
  fee_clearance?: {
    state: "Cleared" | "Outstanding" | "Not Received" | "Released by exception";
    cleared: boolean;
    admission_id: number;
    balance: string | null;
    exception_id: number | null;
  };
  pending_request?: { request_id: number; kind: RequestKind } | null;
};

export type CertificateDetail = Certificate & {
  history: { certificate_id: number; version: number; status: string; holder_name: string; issue_date: DateOnly | null; reason: string | null }[];
  status_history: { from_status: string | null; to_status: string; changed_at: DateTime }[];
};

export type CertificateRequest = {
  request_id: number;
  certificate: {
    certificate_id: number;
    certificate_number: string | null;
    certificate_type: string;
    version: number;
    status: string;
    holder_name: string;
    course: { course_id: number; course_code: string; title: string };
    branch: { branch_id: number; branch_code: string; branch_name: string };
  };
  kind: RequestKind;
  reason: string;
  evidence: string | null;
  changes: Record<string, { from: string; to: string }>;
  status: ApprovalStatus;
  requested_by: UserRef;
  requested_at: DateTime;
  decided_by: UserRef | null;
  decided_at: DateTime | null;
  decision_note: string | null;
  resulting_certificate_id: number | null;
  actions: "decide"[];
};

export type FinancialException = {
  exception_id: number;
  admission: { admission_id: number; admission_code: string };
  outstanding_amount: string;
  certificate_types: string[];
  reason: string;
  status: ApprovalStatus;
  requested_by: UserRef;
  requested_at: DateTime;
  decided_by: UserRef | null;
  decided_at: DateTime | null;
  decision_note: string | null;
  actions: "decide"[];
};

/** Public verification (Module 22 §9). */
export type Verification = {
  certificate_number: string;
  version: number;
  state: "Valid — Current Version" | "Superseded" | "Revoked";
  holder_name: string;
  course: { course_code: string; title: string };
  certificate_type: string;
  branch: { branch_code: string; branch_name: string };
  issue_date: DateOnly | null;
  original_issue_date: DateOnly | null;
  current_version: { version: number; state: string } | null;
};

export type MyCertificates = {
  certificates: Certificate[];
  configuration_pending: { enrolment: EnrolmentRef; state: string; message: string }[];
};

export type CompletionReview = {
  review_id: number;
  enrolment: EnrolmentRef;
  student: Ref;
  status: "Open" | "Decided";
  trainer_recommendation: CompletionDecision | null;
  trainer_comment: string | null;
  recommended_by: UserRef | null;
  recommended_at: DateTime | null;
  decision: CompletionDecision | null;
  decision_reason: string | null;
  decided_by: UserRef | null;
  decided_at: DateTime | null;
};

export type CompletionRow = {
  student: Ref;
  enrolment: EnrolmentRef;
  batch: { batch_id: number; batch_code: string; course_code: string } | null;
  joining_date: DateOnly | null;
  certificate_status: string;
  evidence: Measures | null;
  review: CompletionReview | null;
  can_open: boolean;
  can_decide: boolean;
};

export const certificatesApi = {
  register: (query: Query) => list<Certificate>("/certificates", query),
  mine: () => get<MyCertificates>("/me/certificates"),
  detail: (id: number) => get<CertificateDetail>(`/certificates/${id}`),
  recommend: (id: number, note?: string) => post<Certificate>(`/certificates/${id}/recommendation`, { note }),
  returnToReview: (id: number, reason: string) => post<Certificate>(`/certificates/${id}/return`, { reason }),
  approve: (id: number) => post<Certificate>(`/certificates/${id}/approval`),
  issue: (id: number) => post<Certificate>(`/certificates/${id}/issue`),
  requestChange: (id: number, body: { kind: RequestKind; reason: string; evidence?: string; holder_name?: string }) =>
    post<CertificateRequest>(`/certificates/${id}/change-requests`, body),
  requests: (query: Query) => list<CertificateRequest>("/certificate-requests", query),
  decideRequest: (id: number, decision: "Approved" | "Rejected", note?: string) =>
    post<CertificateRequest>(`/certificate-requests/${id}/decision`, { decision, note }),
  requestException: (id: number, reason: string) => post<FinancialException>(`/certificates/${id}/financial-exception`, { reason }),
  exceptions: (query: Query) => list<FinancialException>("/certificate-financial-exceptions", query),
  decideException: (id: number, decision: "Approved" | "Rejected", note: string) =>
    post<FinancialException>(`/certificate-financial-exceptions/${id}/decision`, { decision, note }),
  verify: (number: string, version?: number) =>
    get<Verification>(`/certificates/verify/${encodeURIComponent(number)}`, version ? { version } : undefined),
  completion: (query: Query) => list<CompletionRow>("/completion-reviews", query),
  openReview: (enrolment_id: number) => post<CompletionReview>("/completion-reviews", { enrolment_id }),
  recommendCompletion: (id: number, recommendation: CompletionDecision, comment?: string) =>
    post<CompletionReview>(`/completion-reviews/${id}/recommendation`, { recommendation, comment }),
  decideCompletion: (id: number, decision: CompletionDecision, reason?: string) =>
    post<CompletionReview>(`/completion-reviews/${id}/decision`, { decision, reason }),
};

export const certificateKeys = {
  register: (query: Query) => ["certificates", "register", query] as const,
  mine: ["certificates", "mine"] as const,
  completion: (query: Query) => ["completion", query] as const,
};

export const useCertificateRegister = (query: Query) => useQuery({ queryKey: certificateKeys.register(query), queryFn: () => certificatesApi.register(query) });
export const useMyCertificates = () => useQuery({ queryKey: certificateKeys.mine, queryFn: certificatesApi.mine });
export const useCompletionRows = (query: Query) => useQuery({ queryKey: certificateKeys.completion(query), queryFn: () => certificatesApi.completion(query) });
