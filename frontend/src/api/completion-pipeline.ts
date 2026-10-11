/** Completion & certificates as one pipeline for the Branch Manager: GET /branch/completion (UX phase U15). */
import { list, type Page, type PageMeta, type Query } from "./client";
import type { DateOnly, DateTime } from "./types";

export const PIPELINE_STAGES = ["ready", "completed", "fee", "issue", "issued"] as const;
export type PipelineStage = (typeof PIPELINE_STAGES)[number];

/** The words on the stage tabs, in pipeline order. */
export const STAGE_LABELS: Record<PipelineStage, string> = {
  ready: "Ready to decide",
  completed: "Completed",
  fee: "Waiting for fee",
  issue: "Ready to issue",
  issued: "Issued",
};

export type PipelineCheck = {
  key: string;
  label: string;
  value: number | string | null;
  threshold: number | string;
  unit: string;
  ok: boolean;
  detail: string | null;
};

export type PipelineAction =
  "decide" | "start_review" | "approve" | "return" | "issue" | "recommend" | "request_correction" | "request_revocation" | "request_reinstatement";

export type PipelineRow = {
  key: string;
  stage: PipelineStage;
  since: DateTime | null;
  student: { student_id: number; student_code: string; full_name: string };
  enrolment: { enrolment_id: number; enrolment_code: string; course: { course_id: number; course_code: string; title: string } };
  branch_id: number;
  batch: { batch_id?: number; batch_code: string; display_name?: string | null } | null;
  evidence: { checks: PipelineCheck[]; all_ok: boolean } | null;
  review: { review_id: number; trainer_recommendation: string | null; trainer_comment: string | null; recommended_by: string | null } | null;
  certificate: {
    certificate_id: number;
    status: string;
    number: string | null;
    version: number;
    type: string;
    issue_date: DateOnly | null;
    pending_request: boolean;
  } | null;
  fee: { state: string; cleared: boolean; balance: string | null; admission_id?: number; exception_id?: number | null } | null;
  actions: PipelineAction[];
  can_request_fee_exception?: boolean;
};

export type PipelineMeta = PageMeta & { counts: Record<PipelineStage, number>; labels: Record<PipelineStage, string> };
export type PipelinePage = Omit<Page<PipelineRow>, "meta"> & { meta: PipelineMeta };

export const completionPipelineApi = {
  list: (query: Query) => list<PipelineRow>("/branch/completion", query) as unknown as Promise<PipelinePage>,
};
