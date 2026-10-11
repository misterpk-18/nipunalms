import { del, download, get, patch, post } from "./client";
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
  /** This course's own figures (safe to add up per admission). */
  summary: {
    fee_total: string;
    verified_paid: string;
    balance: string;
    pending_verification: string;
    payment_completion: "Unpaid" | "Part Paid" | "Paid" | null;
    invoice_numbers: string[];
    installments_scope: "admission" | "invoice";
    invoice_course_count: number;
    receipts: { receipt_number: string; date: DateOnly; amount: string }[];
    as_of: DateTime;
  } | null;
  schedule_key: string | null;
  source: string;
};

/** An instalment schedule, shown once: the CRM keeps instalments per invoice, and one invoice can cover several courses. */
export type FinanceSchedule = {
  schedule_key: string;
  invoice_number: string | null;
  installments_scope: "admission" | "invoice";
  invoice_course_count: number;
  admissions: { admission_id: number; admission_code: string; course: { course_id: number; course_code: string; title: string } }[];
  installments: { installment_no: number; due_date: DateOnly; amount: string; covered: string; balance: string; due_position: string | null }[];
  next_due_date: DateOnly | null;
  next_due_amount: string | null;
  overdue_amount: string;
  as_of: DateTime;
};

/** The "Next payment" card: what is due next, whether it is overdue, and how to pay at the branch. */
export type NextPayment =
  | { state: "unknown" }
  | { state: "paid" }
  | {
      state: "due";
      due_date: DateOnly | null;
      amount: string | null;
      overdue_amount: string;
      is_overdue: boolean;
      courses: string[];
      invoice_number: string | null;
      how_to_pay: { branch: BranchRef; instructions: string | null };
    };

export type EmailCodeAnswer = { sent: boolean; channel: string; expires_in_minutes: number; reason: string | null };

export const profileApi = {
  get: () => get<MyProfile>("/me/profile"),
  setLanguage: (preferred_language: Language) => patch<MyProfile>("/me/profile", { preferred_language }),
  signOutDevice: (sessionId: string) => del<null>(`/auth/sessions/${sessionId}`),
  signOutOthers: () => post<{ signed_out: number }>("/me/devices/sign-out-others"),
  finance: () => get<{ source: string; note: string; admissions: FinanceEntry[]; schedules: FinanceSchedule[]; next_payment: NextPayment }>("/me/finance"),
  receiptPdf: (admissionId: number, receiptNumber: string) =>
    download(`/me/finance/receipts/${admissionId}/${encodeURIComponent(receiptNumber)}/pdf`, undefined, `receipt-${receiptNumber}.pdf`),
  requestEmailCode: (email: string) => post<EmailCodeAnswer>("/me/email/request-code", { email }),
  confirmEmail: (code: string) => post<MyProfile>("/me/email/confirm", { code }),
};
