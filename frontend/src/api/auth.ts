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
  scopes: RoleScope[];
  allowed_branches: BranchRef[];
  workspaces: Workspace[];
  home_route: string;
  student: StudentProfile | null;
};

export type LoginResult = Profile & { token: string; expires_at: DateTime };

export type ActivationCheck = { status: "valid" | "expired" | "used"; student_code_masked: string };

export const authApi = {
  /** `login` is a staff email, a Student ID (NIT-STU-2026-004182) or a student email. */
  login: (login: string, password: string) => post<LoginResult>("/auth/login", { login, password }),
  logout: () => post<null>("/auth/logout"),
  me: () => get<Profile>("/auth/me"),
  reauthenticate: (password: string) => post<null>("/auth/reauthenticate", { password }),
  changePassword: (current_password: string, new_password: string) => post<null>("/auth/change-password", { current_password, new_password }),
  checkActivation: (token: string) => get<ActivationCheck>(`/auth/activation/${encodeURIComponent(token)}`),
  activate: (token: string, password: string) => post<null>("/auth/activate", { token, password }),
};
