/** Shapes shared by many endpoints. Slice-specific types live next to their calls in src/api/<module>.ts. */

/** ISO 8601 timestamp with offset. */
export type DateTime = string;
/** ISO date (YYYY-MM-DD), business dates in IST. */
export type DateOnly = string;

export type BranchRef = { branch_id: number; branch_code: string; branch_name: string };
export type UserRef = { user_id: number; full_name: string };

export type RoleCode = "STUDENT" | "TRAINER" | "ACADEMIC_COORDINATOR" | "BRANCH_MANAGER" | "SUPER_ADMIN" | "FOUNDER_CEO";

export type Workspace = "student" | "trainer" | "academic" | "branch" | "admin" | "founder";

export type Language = "en" | "te";
