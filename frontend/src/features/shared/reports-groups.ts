/** Which figures sit under which heading on the Reports screen. */

export const FIGURE_GROUPS: { title: string; keys: string[] }[] = [
  { title: "Classes and attendance", keys: ["classes_held", "classes_cancelled", "attendance_rate", "at_risk", "recoveries", "content"] },
  { title: "Completion and certificates", keys: ["completed", "not_yet", "certificates", "results"] },
  { title: "Support and issues", keys: ["support_opened", "support_resolved", "support_overdue", "issues"] },
];
