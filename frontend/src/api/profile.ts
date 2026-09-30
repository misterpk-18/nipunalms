import { del, get, patch, post } from "./client";
import type { BranchRef, DateOnly, DateTime, Language } from "./types";

export type Device = { session_id: string; label: string; created_at: DateTime; last_seen_at: DateTime; current: boolean };

export type MyProfile = {
  user: { user_id: number; full_name: string; email: string | null };
  scopes: { role_name: string; branch_name: string | null }[];
  password_changed_at: DateTime | null;
  last_login_at: DateTime | null;
  devices: Device[];
  student: {
    student_code: string;
    full_name: string;
    name_te: string | null;
    email: string | null;
    mobile_masked: string | null;
    mobile_note: string;
    original_branch: BranchRef;
    service_branch: BranchRef;
    activation_status: string;
    preferred_language: Language;
    mfa_status: string;
    recovery: { email_on_file: boolean; method: string };
  } | null;
};

export type FinanceEntry = {
  admission: { admission_id: number; admission_code: string };
  course: { course_id: number; course_code: string; title: string };
  service_branch: BranchRef;
  collecting_branch: BranchRef;
  summary: {
    fee_total: string;
    verified_paid: string;
    balance: string;
    next_due_date: DateOnly | null;
    next_due_amount: string | null;
    receipts: { receipt_number: string; date: DateOnly; amount: string }[];
    as_of: DateTime;
  } | null;
  source: string;
};

export const profileApi = {
  get: () => get<MyProfile>("/me/profile"),
  setLanguage: (preferred_language: Language) => patch<MyProfile>("/me/profile", { preferred_language }),
  signOutDevice: (sessionId: string) => del<null>(`/auth/sessions/${sessionId}`),
  signOutOthers: () => post<{ signed_out: number }>("/me/devices/sign-out-others"),
  finance: () => get<{ source: string; note: string; admissions: FinanceEntry[] }>("/me/finance"),
};
