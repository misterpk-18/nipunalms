import { createFileRoute, redirect } from "@tanstack/react-router";

/** Escalations & Extensions became the Access extensions page. */
export const Route = createFileRoute("/branch/requests")({
  beforeLoad: () => {
    throw redirect({ href: "/branch/extensions", replace: true });
  },
});
