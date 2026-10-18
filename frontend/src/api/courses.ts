/** Course outlines (R6): the modules and topics hang off the course itself. Everyone who can see a course reads the outline; Super Admin and Founder
 * edit it. Course code, title, category, status and tracks are the CRM's and have no edit call (docs/API.md "Course outlines"). */
import { del, get, list, patch, post, put } from "./client";
import type { AssessmentRequirement, Component, CompletionProfile, CourseRef, ModuleContent, OutlineTotals, TopicClass, TopicRow } from "./delivery";
import type { BranchRef } from "./types";

export type CourseUsage = {
  running_batches: number;
  students_waiting: number;
  active_enrolments: number;
  /** Company-wide roles only (Super Admin, Founder): the same counts per branch. */
  by_branch: { branch: BranchRef; running_batches: number; active_enrolments: number }[];
};
export type CourseCounts = { modules: number; topics: number; required_topics: number };
export type CourseFull = CourseRef & { category: string | null; is_combo: boolean; status: string; components?: Component[] };
export type CourseListRow = CourseFull & { counts: CourseCounts; usage: CourseUsage; hours_verified: boolean };

export type OutlineTrack = { component: Component; modules: ModuleContent[]; borrowed_from: CourseRef | null };
export type CourseOutline = {
  course: CourseFull;
  can_edit: boolean;
  counts: CourseCounts;
  modules: ModuleContent[];
  tracks: OutlineTrack[];
  /** Branch Manager, Super Admin and Founder only. */
  totals?: OutlineTotals;
  completion_profile?: CompletionProfile | null;
  assessment_requirements?: AssessmentRequirement[];
  usage?: CourseUsage;
};

export type LibraryVersion = {
  library_version_id: number;
  version_no: number;
  content: { title: string; topics: { title: string }[] };
  change_note: string | null;
  status: string;
};
export type LibraryModule = {
  library_module_id: number;
  module_code: string;
  title: string;
  current_version: LibraryVersion | null;
  versions: LibraryVersion[];
};

export const coursesApi = {
  list: () => get<CourseListRow[]>("/courses"),
  outline: (id: number) => get<CourseOutline>(`/courses/${id}/outline`),
  addModule: (courseId: number, body: { title: string; title_te?: string; position?: number; component_id?: number | null }) =>
    post<ModuleContent>(`/courses/${courseId}/modules`, body),
  updateModule: (id: number, body: { title?: string; title_te?: string | null; position?: number }) => patch<ModuleContent>(`/course-modules/${id}`, body),
  deleteModule: (id: number) => del<null>(`/course-modules/${id}`),
  addTopic: (moduleId: number, body: { title: string; topic_class?: TopicClass; position?: number }) =>
    post<TopicRow>(`/course-modules/${moduleId}/topics`, body),
  updateTopic: (id: number, body: Record<string, unknown>) => patch<TopicRow>(`/course-topics/${id}`, body),
  deleteTopic: (id: number) => del<null>(`/course-topics/${id}`),
  verifyHours: (courseId: number) => post<CourseOutline>(`/courses/${courseId}/hours-verification`),
  setCompletionProfile: (courseId: number, body: CompletionProfile) => put<CourseOutline>(`/courses/${courseId}/completion-profile`, body),
  addRequirement: (courseId: number, body: Record<string, unknown>) => post<AssessmentRequirement>(`/courses/${courseId}/assessment-requirements`, body),
  deleteRequirement: (id: number) => del<null>(`/assessment-requirements/${id}`),
  pinTrack: (courseId: number, body: { component_id: number; pinned_course_id: number | null }) => put<CourseOutline>(`/courses/${courseId}/track-pins`, body),
  reviewEquivalence: (componentId: number, note: string) => post<Component>(`/course-components/${componentId}/equivalence`, { note }),
  library: () => list<LibraryModule>("/course-library", { per_page: 100 }),
  saveToLibrary: (moduleId: number) => post<LibraryModule>(`/course-modules/${moduleId}/library`),
  proposeLibraryVersion: (libraryModuleId: number, body: { module_id: number; change_note: string }) =>
    post<LibraryVersion>(`/course-library/${libraryModuleId}/versions`, body),
  insertLibraryModule: (courseId: number, libraryVersionId: number, componentId?: number | null) =>
    post<ModuleContent>(`/courses/${courseId}/library-modules`, {
      library_version_id: libraryVersionId,
      ...(componentId ? { component_id: componentId } : {}),
    }),
};
