import { createFileRoute, redirect } from "@tanstack/react-router";

/** "Batches, Schedule & People" was split: batches, the waiting list and the schedule have their own screens (UX phase U14). */
export const Route = createFileRoute("/branch/operations")({
  beforeLoad: () => {
    throw redirect({ to: "/branch/batches", replace: true });
  },
});
