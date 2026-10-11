import { createFileRoute, redirect } from "@tanstack/react-router";

/** Academic Reports and Certificates & Reports became Reports (UX phase U15). */
export const Route = createFileRoute("/branch/academic-reports")({
  beforeLoad: ({ location }) => {
    throw redirect({ href: `/branch/reports${location.searchStr}`, replace: true });
  },
});
