import { createFileRoute, redirect } from "@tanstack/react-router";

/** Recording Exceptions became Issues and Recordings (UX phase U15). */
export const Route = createFileRoute("/branch/recording-exceptions")({
  beforeLoad: ({ location }) => {
    throw redirect({ href: `/branch/recordings${location.searchStr}`, replace: true });
  },
});
