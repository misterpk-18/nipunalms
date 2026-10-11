import { createFileRoute, redirect } from "@tanstack/react-router";

/** Reviews became Marks & results (UX phase U15). */
export const Route = createFileRoute("/branch/assessments")({
  beforeLoad: ({ location }) => {
    throw redirect({ href: `/branch/results${location.searchStr}`, replace: true });
  },
});
