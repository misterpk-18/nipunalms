import { createFileRoute, redirect } from "@tanstack/react-router";

/** Results are a tab of My Progress now. */
export const Route = createFileRoute("/results")({
  beforeLoad: () => {
    throw redirect({ to: "/progress", search: { tab: "results" }, replace: true });
  },
});
