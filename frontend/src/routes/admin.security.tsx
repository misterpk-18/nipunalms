import { createFileRoute, redirect } from "@tanstack/react-router";

/** Moved (UX phase U17): the old address keeps working and lands on its new screen. */
export const Route = createFileRoute("/admin/security")({
  beforeLoad: ({ location }) => {
    throw redirect({ href: `/admin/setup${location.searchStr}`, replace: true });
  },
});
