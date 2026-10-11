import { createFileRoute, redirect } from "@tanstack/react-router";

/** Content Review became Content & questions (UX phase U15); old links and notifications still work. */
export const Route = createFileRoute("/branch/content-review")({
  beforeLoad: ({ location }) => {
    throw redirect({ href: `/branch/content${location.searchStr}`, replace: true });
  },
});
