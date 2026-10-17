import { createFileRoute, redirect } from "@tanstack/react-router";

/** Old /academic/* screens now live under /branch/* (the Academic Coordinator role was merged into the Branch Manager). */
const MOVED: Record<string, string> = { reports: "reports", "meet-operations": "class-day", operations: "batches" };

export const Route = createFileRoute("/academic/$")({
  validateSearch: (search: Record<string, unknown>): Record<string, unknown> => search,
  beforeLoad: ({ params, search }) => {
    const rest = params._splat ?? "";
    // The CRM's "Open in LMS" link (/academic/batches?crm_admission_id=…&student=<student code>) lands on that student in Waiting for a batch
    const student = typeof search["student"] === "string" ? search["student"].trim() : "";
    if (rest === "batches" && student) throw redirect({ to: "/branch/waiting", search: { q: student }, replace: true });
    throw redirect({ href: `/branch/${MOVED[rest] ?? rest}`, replace: true });
  },
});
