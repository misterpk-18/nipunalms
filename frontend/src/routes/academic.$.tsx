import { createFileRoute, redirect } from "@tanstack/react-router";

/** Old /academic/* screens now live under /branch/* (the Academic Coordinator role was merged into the Branch Manager). */
const MOVED: Record<string, string> = { reports: "academic-reports", "meet-operations": "class-day", operations: "batches" };

export const Route = createFileRoute("/academic/$")({
  beforeLoad: ({ params }) => {
    const rest = params._splat ?? "";
    throw redirect({ href: `/branch/${MOVED[rest] ?? rest}`, replace: true });
  },
});
