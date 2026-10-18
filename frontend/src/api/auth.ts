import { get, post } from "./client";
import type { BranchRef, DateTime, Language, RoleCode, Workspace } from "./types";

export type SessionUser = {
  user_id: number;
  full_name: string;
  email: string | null;
  must_change_password: boolean;
  student_id: number | null;
};

export type RoleScope = {
  scope_id: number;
  role_code: RoleCode;
  role_name: string;
  branch_id: number | null;
  branch_code: string | null;
  branch_name: string | null;
  is_company_wide: boolean;
};

export type StudentProfile = {
  student_id: number;
  student_code: string;
  full_name: string;
  name_te: string | null;
  preferred_language: Language;
  activation_status: string;
  service_branch_id: number;
};

export type Profile = {
  user: SessionUser;
  /** The session's one role (role separation R3). */
  role?: { role_code: RoleCode; role_name: string };
  /** The one workspace of that role; `workspaces` below always holds just this. */
  workspace?: Workspace;
  /** A Branch Manager's branch for this session; null for every other role and while a pick is pending. */
  branch?: BranchRef | null;
  /** A Branch Manager with several branches has signed in but not picked one: `branches` lists the choices and nothing else works. */
  needs_branch?: boolean;
  branches?: BranchRef[];
  scopes: RoleScope[];
  allowed_branches: BranchRef[];
  workspaces: Workspace[];
  home_route: string;
  student: StudentProfile | null;
};

export type LoginResult = Profile & { token: string; expires_at: DateTime };

export type ActivationCheck = {
  kind: "student" | "staff";
  status: "valid" | "expired" | "used" | "revoked";
  full_name: string;
  /** Masked: NIT-STU-2026-••••82. Students only. */
  student_code: string | null;
  /** Masked: r••••@nipuna.test. Staff only. */
  email: string | null;
  expires_at: DateTime;
  password_min_length: number;
};

/** Activating signs the person in: the login response plus the Student ID to show on the success step. */
export type ActivationResult = LoginResult & { activated: true; student_code: string | null };

export const authApi = {
  /** `login` is a staff email, a Student ID (NIT-STU-2026-004182) or a student email. */
  login: (login: string, password: string, branch_id?: number) => post<LoginResult>("/auth/login", { login, password, ...(branch_id ? { branch_id } : {}) }),
  /** Branch Manager with several branches: pick the branch for this session (answers the profile). */
  selectBranch: (branch_id: number) => post<Profile>("/auth/branch", { branch_id }),
  /** Ends the session; the person signs in again and picks a branch. */
  changeBranch: () => post<null>("/auth/change-branch"),
  logout: () => post<null>("/auth/logout"),
  me: () => get<Profile>("/auth/me"),
  reauthenticate: (password: string) => post<null>("/auth/reauthenticate", { password }),
  changePassword: (current_password: string, new_password: string) => post<null>("/auth/change-password", { current_password, new_password }),
  checkActivation: (token: string) => get<ActivationCheck>(`/auth/activation/${encodeURIComponent(token)}`),
  activate: (token: string, password: string) => post<ActivationResult>("/auth/activate", { token, password }),
  /** Always answers "If the account exists, we've sent a code", whether or not the account exists. */
  requestResetCode: (login: string) => post<{ message: string }>("/auth/reset-code", { login }),
  resetPassword: (login: string, code: string, new_password: string) => post<null>("/auth/reset", { login, code, new_password }),
};
