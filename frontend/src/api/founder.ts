/** The Founder's inbox and its decisions (UX phase U16; docs/API.md §4.20). Each item carries the record as its own screen shows it. */
import { useQuery } from "@tanstack/react-query";
import { get, post, put } from "./client";
import type { Correction } from "./attendance";
import type { CertificateRequest, FinancialException } from "./certificates";
import type { StaffExtensionRequest } from "./content";
import type { RescheduleRequest } from "./delivery";
import type { DateTime } from "./types";

export type InboxGroup = "certificates" | "access" | "other";
export type InboxKind = "certificate" | "fee_exception" | "access_extension" | "ai_budget" | "bm_reschedule" | "bm_correction";

export type AiBudgetDetail = { state: "Configuration Pending" } | { state: "Configured"; amount_inr: number };

type Base<K extends InboxKind, D> = {
  key: string;
  kind: K;
  id: number | string;
  /** What it is, in plain words ("Approve a certificate for Asha"). */
  title: string;
  where: string | null;
  /** When it started waiting; null for the AI budget. */
  since: DateTime | null;
  /** The button on the list ("Review"). */
  action: string;
  /** The Founder page that lists this kind. */
  to: string;
  from_branch_manager: boolean;
  /** False when the person could decide this kind but raised the request themselves: an independent approver decides it. */
  can_decide: boolean;
  detail: D;
};

export type InboxItem =
  | Base<"certificate", CertificateRequest>
  | Base<"fee_exception", FinancialException>
  | Base<"access_extension", StaffExtensionRequest>
  | Base<"ai_budget", AiBudgetDetail>
  | Base<"bm_reschedule", RescheduleRequest & { can_decide: boolean }>
  | Base<"bm_correction", Correction & { can_decide: boolean }>;

export type FounderInbox = {
  as_of: DateTime;
  total: number;
  counts: Record<InboxKind, number>;
  items: InboxItem[];
  /** False until the CRM has sent finance figures; the CRM tiles stay hidden until then. */
  crm_connected: boolean;
};

export const founderApi = {
  inbox: (group?: InboxGroup) => get<FounderInbox>("/founder/inbox", { group }),
  approveAiBudget: (amountInr: number) => put<AiBudgetDetail>("/founder/ai-budget", { amount_inr: amountInr }),
};

export const founderKeys = { inbox: (group?: InboxGroup) => ["founder", "inbox", group ?? "all"] as const };

/** The Founder's inbox, or one page of it; refreshed every minute with the nav badges. */
export const useFounderInbox = (group?: InboxGroup) =>
  useQuery({ queryKey: founderKeys.inbox(group), queryFn: () => founderApi.inbox(group), refetchInterval: 60_000 });
