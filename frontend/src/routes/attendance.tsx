import { createFileRoute, redirect } from "@tanstack/react-router";

/** Attendance is a tab of My Progress now. */
export const Route = createFileRoute("/attendance")({
  beforeLoad: () => {
    throw redirect({ to: "/progress", search: { tab: "attendance" }, replace: true });
  },
});
