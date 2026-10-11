/** The Issues inbox: everything wrong or stuck, from every source, in one paged list (UX plan U15). */
import { get, list, post, type PageMeta, type Query } from "./client";
import type { DateTime, UserRef } from "./types";

export const ISSUE_TYPES = ["students", "classes", "recordings", "support", "results", "access", "system"] as const;
export type IssueType = (typeof ISSUE_TYPES)[number];

export type Issue = {
  id: string;
  /** Where the issue comes from; with `source_id` it addresses the notes. */
  source: string;
  source_id: number;
  reference: string;
  type: IssueType;
  type_label: string;
  title: string;
  detail: string | null;
  branch: { branch_id: number; branch_code: string; branch_name: string } | null;
  owner: UserRef | null;
  owner_label: string | null;
  awaiting_owner: boolean;
  opened_at: DateTime;
  age_days: number;
  state: string;
  step_count: number;
  last_step_at: DateTime | null;
  go_fix: { to: string; search: Record<string, unknown> | null };
  can_note: boolean;
  /** A Super Admin may hand it to someone, unless its own screen already names the owner. */
  can_assign: boolean;
};

export type IssueCounts = Record<IssueType | "all", number>;
export type IssuePage = { data: Issue[]; meta: PageMeta & { counts: IssueCounts } };

export type IssueNote = { step_id: number; reason: string; logged_by: UserRef; logged_at: DateTime };

export const issuesApi = {
  // client.list() passes the whole meta through, so the type counts arrive with the page.
  list: (query: Query) => list<Issue>("/issues", query) as unknown as Promise<IssuePage>,
  notes: (issue: Pick<Issue, "source" | "source_id">) => get<IssueNote[]>(`/exceptions/${issue.source}/${issue.source_id}/steps`),
  assign: (issue: Pick<Issue, "source" | "source_id">, assignee_user_id: number, note?: string) =>
    post<unknown>(`/exceptions/${issue.source}/${issue.source_id}/assign`, { assignee_user_id, ...(note ? { note } : {}) }),
  addNote: (issue: Pick<Issue, "source" | "source_id">, reason: string) => post<unknown>(`/exceptions/${issue.source}/${issue.source_id}/steps`, { reason }),
};
