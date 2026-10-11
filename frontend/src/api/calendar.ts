/** The academic calendar: company holidays and branch closures, edit and cancel with their impact (UX phase U17). */
import { get, list, patch, post, type Page } from "./client";
import type { BranchRef, DateOnly, DateTime, UserRef } from "./types";

export type ClosureKind = "Company Holiday" | "Branch Closure";
export type ClosureStatus = "Pending" | "Approved" | "Rejected" | "Cancelled";

export type Closure = {
  closure_id: number;
  kind: ClosureKind;
  branch: BranchRef | null;
  starts_on: DateOnly;
  ends_on: DateOnly;
  title: string;
  reason: string | null;
  status: ClosureStatus;
  requested_by: UserRef;
  requested_at: DateTime;
  decided_by: UserRef | null;
  decision_note: string | null;
  cancelled_at: DateTime | null;
  cancel_reason: string | null;
};

/** What a change touches: the classes inside the dates, and how many are new to the closure or no longer covered. */
export type ClosureImpact = Closure & {
  affected_count: number;
  affected_sessions: {
    session_id: number;
    session_code: string;
    title: string;
    starts_at: DateTime;
    batch: { batch_code: string; display_name?: string | null };
  }[];
  newly_affected_count?: number;
  freed_count?: number;
  saved: boolean;
};

export type ClosureFilters = { from?: string; to?: string; status?: string; sort?: "upcoming" | "newest"; page?: number; per_page?: number };

export const calendarKeys = { all: ["calendar", "closures"] as const };

export const calendarApi = {
  list: (filters: ClosureFilters): Promise<Page<Closure>> => list<Closure>("/calendar/closures", { per_page: 20, ...filters }),
  /** Every entry in a window (a month grid), however many pages that takes. */
  inWindow: async (from: string, to: string): Promise<Closure[]> => {
    const rows: Closure[] = [];
    for (let page = 1; ; page++) {
      const result = await list<Closure>("/calendar/closures", { from, to, page, per_page: 100 });
      rows.push(...result.data);
      if (page >= result.meta.pages) return rows;
    }
  },
  get: (id: number) => get<Closure>(`/calendar/closures/${id}`),
  create: (body: { kind: ClosureKind; branch_id: number | null; starts_on: string; ends_on: string; title: string; reason?: string }) =>
    post<Closure>("/calendar/closures", body),
  update: (id: number, body: { title?: string; reason?: string | null; starts_on?: string; ends_on?: string; dry_run?: boolean }) =>
    patch<ClosureImpact>(`/calendar/closures/${id}`, body),
  cancel: (id: number, body: { reason: string; dry_run?: boolean }) => post<ClosureImpact>(`/calendar/closures/${id}/cancel`, body),
  decide: (id: number, decision: "Approved" | "Rejected", note?: string) => post<Closure>(`/calendar/closures/${id}/decision`, { decision, note }),
};
