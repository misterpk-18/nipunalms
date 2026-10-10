import { createFileRoute, redirect } from "@tanstack/react-router";

/** The test list is part of Tasks & Tests now. */
export const Route = createFileRoute("/tests/")({
  beforeLoad: () => {
    throw redirect({ to: "/tasks", replace: true });
  },
});
