/** Content library, recordings, recording exceptions and access-extension requests (slice S2). */
import { API_BASE, ApiError, get, getToken, list, post, patch, upload, type Page } from "./client";
import type { BranchRef, DateOnly, DateTime, UserRef } from "./types";

export const CONTENT_TYPES = ["PDF", "Notes", "Dataset", "Code", "Lab", "Practice material", "Link", "Video link"] as const;
export type ContentType = (typeof CONTENT_TYPES)[number];
export const LINK_TYPES: readonly string[] = ["Link", "Video link"];
export type ContentStatus = "Draft" | "Submitted" | "Under Review" | "Approved" | "Released" | "Changes Requested" | "Rejected" | "Retired";

type CourseRef = { course_id: number; course_code: string; title: string };
type BatchRef = { batch_id: number; batch_code: string; course_code: string };

export type ContentVersion = {
  content_version_id: number;
  version_no: number;
  storage_kind: "File" | "Link";
  original_filename: string | null;
  file_size_bytes: number | null;
  url: string | null;
  change_summary: string | null;
  status: ContentStatus;
  uploaded_by: UserRef;
  uploaded_at: DateTime;
  released_at: DateTime | null;
};

export type ContentReview = { review_id: number; version_no: number; action: string; actor: UserRef; comment: string | null; acted_at: DateTime };

export type ContentItem = {
  content_item_id: number;
  item_code: string;
  title: string;
  content_type: ContentType;
  description: string | null;
  language: "en" | "te";
  course: CourseRef;
  curriculum_version: { curriculum_version_id: number; version_label: string } | null;
  module: { module_id: number; title: string } | null;
  topic: { topic_id: number; title: string } | null;
  branch: BranchRef;
  batch: BatchRef | null;
  download_allowed: boolean;
  status: ContentStatus;
  owner: UserRef;
  version_no: number;
  released_version_no: number | null;
  storage_kind: "File" | "Link";
  original_filename: string | null;
  url: string | null;
  submitted_at: DateTime | null;
  updated_at: DateTime;
  retire_reason: string | null;
  versions?: ContentVersion[];
  reviews?: ContentReview[];
};

export type AccessState = { state: "Pending" | "Available" | "Expired"; expiry: DateOnly | null; extended: boolean };

export type StudentResource = {
  content_item_id: number;
  item_code: string;
  title: string;
  content_type: ContentType;
  description: string | null;
  course: CourseRef;
  track: { track_code: string; track_name: string } | null;
  module: { module_id: number; title: string } | null;
  topic: { topic_id: number; title: string } | null;
  storage_kind: "File" | "Link";
  original_filename: string | null;
  version_no: number;
  download_allowed: boolean;
  enrolment: { enrolment_id: number; enrolment_code: string };
  access: AccessState;
};

export type OpenedResource = {
  storage_kind: "File" | "Link";
  url: string | null;
  original_filename: string | null;
  download_allowed: boolean;
  inline: boolean;
};

export type PlacementOption = {
  batch: BatchRef;
  course: CourseRef;
  branch: BranchRef;
  versions: {
    curriculum_version_id: number;
    version_label: string;
    track_name: string | null;
    modules: { module_id: number; title: string; topics: { topic_id: number; title: string }[] }[];
  }[];
};

export const RECORDING_STATUSES = ["Processing", "Released", "Partial", "Held", "Unavailable", "Expired"] as const;
export type RecordingStatus = (typeof RECORDING_STATUSES)[number];

type SessionSummary = {
  session_id: number;
  session_code: string;
  title: string;
  starts_at: DateTime;
  ends_at: DateTime;
  mode: string;
  state: string;
  batch: BatchRef;
  branch: BranchRef;
  trainer: UserRef | null;
};

export type Recording = {
  recording_id: number;
  recording_code: string;
  session: SessionSummary;
  part_no: number;
  status: RecordingStatus;
  source: string;
  media_ref: string | null;
  duration_minutes: number | null;
  download_allowed: boolean;
  released_at: DateTime | null;
  hold_reason: string | null;
  partial_note: string | null;
};

export type StudentRecording = {
  recording_id: number;
  recording_code: string;
  session: { session_id: number; session_code: string; title: string; starts_at: DateTime; mode: string; trainer: UserRef };
  course: CourseRef;
  track: { track_code: string; track_name: string } | null;
  topic: { topic_id: number; title: string } | null;
  status: RecordingStatus;
  status_note: string | null;
  duration_minutes: number | null;
  download_allowed: boolean;
  enrolment: { enrolment_id: number; enrolment_code: string };
  access: AccessState;
  playable: boolean;
};

export type Playback = {
  recording_code: string;
  session_title: string;
  status: RecordingStatus;
  status_note: string | null;
  playback: { mode: "stream" | "download"; source: string; integration_status: string; available: boolean; message: string | null };
};

export type RecordingException = {
  exception_id: number;
  exception_code: string;
  session: { session_id: number; session_code: string; title: string; starts_at: DateTime; mode: string };
  batch: BatchRef;
  branch: BranchRef;
  issue_type: "Partial" | "Held" | "Unavailable" | "Integration Unavailable";
  issue: string;
  status: "Open" | "In Progress" | "Resolved";
  owner: string;
  owner_role: string;
  owner_user: UserRef | null;
  opened_at: DateTime;
  age_hours: number;
  escalation: string | null;
  resolved_at: DateTime | null;
  resolution_note: string | null;
};

export type ExtensionRequest = {
  request_id: number;
  request_code: string;
  enrolment: { enrolment_id: number; enrolment_code: string; course: CourseRef };
  student: { student_id: number; student_code: string; full_name: string };
  branch: BranchRef;
  scope: "Recording" | "Material" | "Both";
  reason: string;
  status: "Pending" | "Approved" | "Rejected";
  needs_exception: boolean;
  original_expiry: DateOnly;
  approved_expiry: DateOnly | null;
  requested_at: DateTime;
  decided_by: UserRef | null;
  decision_note: string | null;
};

export type AccessOverview = {
  enrolment: { enrolment_id: number; enrolment_code: string; course: CourseRef };
  joining_date: DateOnly | null;
  first_expiry: DateOnly | null;
  second_expiry: DateOnly | null;
  recording: AccessState;
  material: AccessState;
  can_request: { Recording: boolean; Material: boolean };
  pending_requests: ExtensionRequest[];
};

export type Query = Record<string, string | number | boolean | null | undefined>;

export const contentApi = {
  // staff content
  items: (query?: Query): Promise<Page<ContentItem>> => list<ContentItem>("/content-items", query),
  item: (id: number) => get<ContentItem>(`/content-items/${id}`),
  options: () => get<PlacementOption[]>("/content-items/options"),
  create: (form: FormData) => upload<ContentItem>("/content-items", form),
  addVersion: (id: number, form: FormData) => upload<ContentItem>(`/content-items/${id}/versions`, form),
  update: (id: number, body: Record<string, unknown>) => patch<ContentItem>(`/content-items/${id}`, body),
  submit: (id: number) => post<ContentItem>(`/content-items/${id}/submit`),
  review: (id: number, body: { decision: "start" | "approve" | "request_changes" | "reject"; comment?: string; release?: boolean }) =>
    post<ContentItem>(`/content-items/${id}/review`, body),
  release: (id: number) => post<ContentItem>(`/content-items/${id}/release`),
  retire: (id: number, reason: string) => post<ContentItem>(`/content-items/${id}/retire`, { reason }),
  open: (id: number) => post<OpenedResource>(`/content-items/${id}/open`),
  // student library
  resources: (query?: Query) => get<StudentResource[]>("/me/resources", query),
  recordings: (query?: Query) => get<StudentRecording[]>("/me/recordings", query),
  access: () => get<AccessOverview[]>("/me/access"),
  watch: (id: number) => post<Playback>(`/recordings/${id}/watch`),
  // staff recordings
  staffRecordings: (query?: Query): Promise<Page<Recording>> => list<Recording>("/recordings", query),
  registerRecording: (body: Record<string, unknown>) => post<Recording>("/recordings", body),
  updateRecording: (id: number, body: Record<string, unknown>) => patch<Recording>(`/recordings/${id}`, body),
  recordingAction: (id: number, action: "release" | "hold" | "partial" | "unavailable", body: Record<string, unknown> = {}) =>
    post<Recording>(`/recordings/${id}/${action}`, body),
  exceptions: (query?: Query): Promise<Page<RecordingException>> => list<RecordingException>("/recording-exceptions", query),
  startException: (id: number) => post<RecordingException>(`/recording-exceptions/${id}/start`),
  resolveException: (id: number, resolution_note: string) => post<RecordingException>(`/recording-exceptions/${id}/resolve`, { resolution_note }),
  // access extensions
  requests: (query?: Query): Promise<Page<ExtensionRequest>> => list<ExtensionRequest>("/access-extension-requests", query),
  requestExtension: (body: { enrolment_id: number; scope: string; reason: string }) => post<ExtensionRequest>("/access-extension-requests", body),
  decide: (id: number, body: { decision: "approve" | "reject"; note?: string; new_expiry?: string }) =>
    post<ExtensionRequest>(`/access-extension-requests/${id}/decision`, body),
};

/** Fetch a content file with the session token and hand it to the browser (new tab to view, or save as a download). */
export async function openContentFile(id: number, filename: string | null, download: boolean): Promise<void> {
  const token = getToken();
  const response = await fetch(`${API_BASE}/content-items/${id}/file${download ? "?download=true" : ""}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(response.status, payload?.error?.code ?? "HTTP_ERROR", payload?.error?.message ?? `Could not open the file (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  if (download || !response.headers.get("Content-Disposition")?.startsWith("inline")) {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename ?? "download";
    link.click();
  } else {
    window.open(url, "_blank", "noopener");
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value.length === 10 ? `${value}T00:00:00+05:30` : value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return `${new Date(value).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" })} IST`;
}

export function accessText(access: AccessState): string {
  if (access.state === "Pending") return "Pending — no Joining Date yet";
  const until = `Until ${formatDate(access.expiry)}`;
  return access.state === "Expired" ? `Expired ${formatDate(access.expiry)}` : until;
}
