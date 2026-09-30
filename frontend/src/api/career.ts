import { API_BASE, ApiError, get, getToken, post, put, upload } from "./client";
import type { DateOnly, DateTime } from "./types";

export type Skill = { name: string; confidence: "Verified" | "Student Reported" | "Verification Pending" };

export type CareerProfile = {
  opted_in: boolean;
  opted_in_at: DateTime | null;
  support_start: DateOnly | null;
  support_end: DateOnly | null;
  preferred_roles: string[];
  preferred_locations: string[];
  work_mode: string | null;
  qualification: string | null;
  graduation_year: number | null;
  experience_level: string | null;
  skills: Skill[];
  portfolio_url: string | null;
  availability: string | null;
  sharing_consent: boolean;
  sharing_consent_at: DateTime | null;
  readiness: "Not Assessed" | "In Preparation" | "Ready for referral";
  readiness_note: string | null;
  completeness: { percent: number; missing: string[] };
};

export type CvVersion = {
  cv_id: number;
  version_no: number;
  label: string;
  original_filename: string;
  review_status: "Pending Review" | "Reviewed" | "Changes Requested" | "Superseded";
  review_feedback: string | null;
  uploaded_at: DateTime;
};

export type OpportunityItem = {
  opportunity_id: number;
  opportunity_code: string;
  title: string;
  employer_name: string;
  employment_type: string;
  work_mode: string;
  location: string | null;
  description: string | null;
  required_skills: string[];
  compensation_text: string;
  openings: number | null;
  closing_date: DateOnly | null;
  applied: boolean;
};

export type ApplicationItem = {
  application_id: number;
  status: string;
  closed: boolean;
  interview_round: string | null;
  interview_at: DateTime | null;
  status_note: string | null;
  applied_at: DateTime;
  cv: { cv_id: number; version_no: number; label: string } | null;
  opportunity: { opportunity_id: number; title: string; employer_name: string; location: string | null };
};

export type OutcomeItem = {
  outcome_id: number;
  outcome_type: string;
  employer_name: string;
  role_title: string;
  event_date: DateOnly;
  verification_status: "Pending Verification" | "Verified" | "Rejected";
};

export type CareerOverview = {
  notice: string;
  profile: CareerProfile;
  cvs: CvVersion[];
  opportunities: OpportunityItem[];
  applications: ApplicationItem[];
  outcomes: OutcomeItem[];
  next_action: string;
};

export type ProfileUpdate = Partial<
  Pick<
    CareerProfile,
    | "opted_in"
    | "preferred_roles"
    | "preferred_locations"
    | "work_mode"
    | "qualification"
    | "graduation_year"
    | "experience_level"
    | "portfolio_url"
    | "availability"
  >
> & { skills?: string[] };

export const careerApi = {
  overview: () => get<CareerOverview>("/me/career"),
  updateProfile: (body: ProfileUpdate) => put<CareerOverview>("/me/career/profile", body),
  setConsent: (sharing_consent: boolean) => put<CareerOverview>("/me/career/consent", { sharing_consent }),
  uploadCv: (file: File, label: string) => {
    const form = new FormData();
    form.set("file", file);
    if (label) form.set("label", label);
    return upload<CvVersion>("/me/career/cvs", form);
  },
  apply: (opportunityId: number) => post<ApplicationItem>(`/me/career/opportunities/${opportunityId}/apply`),
  withdraw: (applicationId: number) => post<ApplicationItem>(`/me/career/applications/${applicationId}/withdraw`),
  /** Downloads a CV file with the session header attached. */
  downloadCv: async (cv: CvVersion) => {
    const response = await fetch(`${API_BASE}/cv-documents/${cv.cv_id}/download`, { headers: { Authorization: `Bearer ${getToken() ?? ""}` } });
    if (!response.ok) throw new ApiError(response.status, "HTTP_ERROR", `Download failed (${response.status})`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = cv.original_filename;
    link.click();
    URL.revokeObjectURL(url);
  },
};
