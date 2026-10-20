import { createFileRoute, redirect } from "@tanstack/react-router";

/** Moved (UX phase U17): the old address keeps working and lands on its new screen. */
export const Route = createFileRoute("/admin/exceptions")({
  beforeLoad: ({ location }) => {
    throw redirect({ to: "/admin/issues", search: location.search as Record<string, never>, replace: true });
  },
});
