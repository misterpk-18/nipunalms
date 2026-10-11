import { createFileRoute, redirect } from "@tanstack/react-router";

/** Escalations & Extensions became a tab of Student support (UX phase U15). */
export const Route = createFileRoute("/branch/requests")({
  beforeLoad: () => {
    throw redirect({ href: "/branch/support?tab=extensions", replace: true });
  },
});
