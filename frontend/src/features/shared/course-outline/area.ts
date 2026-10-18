/** Where the Courses pages live: the Branch Manager's read-only copy, and the Super Admin's and Founder's editable ones. */
export type CoursesBase = "/branch" | "/admin" | "/founder";

/** A route inside the area, for a typed `Link` (`/branch/courses`, `/admin/courses/$id`). */
export const coursesTo = (base: CoursesBase, suffix: "" | "/$id") => `${base}/courses${suffix}` as never;
