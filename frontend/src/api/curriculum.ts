/** Curriculum calls that the shared delivery API does not type yet: the submit checklist and the auto-named draft. */
import { get, post } from "./client";
import type { CurriculumVersion } from "./delivery";

export type ChecklistStepKey = "tracks" | "modules" | "topics" | "hours" | "rules" | "assessments";

export type ChecklistTopicItem = { topic_id: number; module_id: number; title: string; module_title: string; missing: string[] };
export type ChecklistStep = {
  key: ChecklistStepKey;
  label: string;
  required: boolean;
  done: boolean;
  hint: string;
  /** Incomplete topics for the `topics` step; `{ title }` for modules and tracks. */
  items: (ChecklistTopicItem | { title: string })[];
};
export type Checklist = { steps: ChecklistStep[]; ready: boolean; next: ChecklistStepKey | null };

export type VersionWithChecklist = CurriculumVersion & { checklist?: Checklist };

export type NewDraft = {
  course_id: number;
  component_id?: number | null;
  /** Leave out: the server names the draft (CV 5.2). */
  version_label?: string;
  copy_from_version_id?: number | null;
  /** True starts an empty draft instead of copying the Active version. */
  blank?: boolean;
};

export const curriculumApi = {
  version: (id: number) => get<VersionWithChecklist>(`/curriculum-versions/${id}`),
  createDraft: (body: NewDraft) => post<CurriculumVersion>("/curriculum-versions", body),
};

export const isTopicItem = (item: ChecklistStep["items"][number]): item is ChecklistTopicItem => "topic_id" in item;
