import { createFileRoute, redirect } from "@tanstack/react-router";

/** Moved (UX phase U17): the old address keeps working and lands on its new screen. */
export const Route = createFileRoute("/admin/integrations")({
  beforeLoad: ({ location }) => {
    throw redirect({ to: "/admin/setup", search: location.search as Record<string, never>, replace: true });
  },
});
