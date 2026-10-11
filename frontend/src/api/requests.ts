/** The signed-in staff member's own requests (`GET /me/requests`): reschedules and attendance corrections. */
import { useQuery } from "@tanstack/react-query";
import { get } from "./client";
import type { DateTime, UserRef } from "./types";

export type MyRequest = {
  kind: "reschedule" | "correction";
  id: number;
  status: "Pending" | "Approved" | "Rejected";
  title: string;
  /** What was asked, in one line ("From Tue 13 Oct ... to ..."). */
  summary: string;
  reason: string;
  requested_at: DateTime;
  decided_by: UserRef | null;
  decided_at: DateTime | null;
  decision_note: string | null;
  /** Who decides while it waits ("Branch Manager"). */
  decides: string;
  session: { session_id: number; title: string; starts_at: DateTime; ends_at: DateTime; batch: { batch_id: number; batch_code: string; course_code: string } };
};
export type MyRequests = { items: MyRequest[]; counts: { waiting: number; decided: number } };

export const requestsApi = { mine: () => get<MyRequests>("/me/requests") };
export const requestKeys = { mine: ["me", "requests"] as const };
export const useMyRequests = () => useQuery({ queryKey: requestKeys.mine, queryFn: requestsApi.mine });
