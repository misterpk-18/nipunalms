import { createFileRoute, redirect } from "@tanstack/react-router";

/** Meet Operations became Class day (UX phase U14); old links and notifications still work. */
export const Route = createFileRoute("/branch/meet-operations")({
  beforeLoad: () => {
    throw redirect({ to: "/branch/class-day", replace: true });
  },
});
