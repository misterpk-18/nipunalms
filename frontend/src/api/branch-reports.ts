/** Reports (Branch Manager, Super Admin, Founder): figures with drill-down links, per-batch progress and monthly trends (UX plan U15). */
import { download, get, type Query } from "./client";
import type { DateOnly } from "./types";

export type ReportPeriodKey = "this_month" | "last_month" | "last_90" | "custom";

export type ReportFigure = {
  key: string;
  label: string;
  /** null means there is nothing to measure yet; never show it as 0. */
  value: number | null;
  unit: string;
  hint: string | null;
  /** The screen with the records behind the figure in the session's own workspace; null when this role has none. */
  drill: { to: string; search: Record<string, unknown> | null } | null;
};

export type ReportBatchRow = {
  batch: { batch_id: number; batch_code: string; display_name?: string | null; course_code?: string };
  state: string;
  students: number;
  avg_delivery: number | null;
  avg_attendance: number | null;
  avg_required_learning: number | null;
  alerts: number;
  drill: { to: string; search: Record<string, unknown> | null } | null;
};

export type ReportTrend = {
  month: string;
  label: string;
  classes_held: number;
  attendance_rate: number | null;
  completed: number;
  certificates: number;
  support_opened: number;
};

export type BranchReport = {
  period: { key: ReportPeriodKey; label: string; from: DateOnly; to: DateOnly };
  periods: Record<ReportPeriodKey, string>;
  scope: { branch_id: number | null };
  figures: ReportFigure[];
  batches: ReportBatchRow[];
  trends: ReportTrend[];
};

export type ReportSection = "figures" | "batches" | "trends" | "certificates";

export const branchReportsApi = {
  report: (query: Query) => get<BranchReport>("/branch/reports", query),
  exportCsv: (section: ReportSection, query: Query) => download("/branch/reports/export", { section, ...query }, `report-${section}.csv`),
};
