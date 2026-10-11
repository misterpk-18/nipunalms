import { createFileRoute, redirect } from "@tanstack/react-router";

/** Exceptions and Recording Exceptions became the Issues inbox (UX phase U15). */
export const Route = createFileRoute("/branch/exceptions")({
  beforeLoad: ({ location }) => {
    throw redirect({ href: `/branch/issues${location.searchStr}`, replace: true });
  },
});
