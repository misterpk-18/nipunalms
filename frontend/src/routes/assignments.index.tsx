import { createFileRoute, redirect } from "@tanstack/react-router";

/** The assignment list is part of Tasks & Tests now. */
export const Route = createFileRoute("/assignments/")({
  beforeLoad: () => {
    throw redirect({ to: "/tasks", replace: true });
  },
});
