import { createFileRoute, redirect } from "@tanstack/react-router";

/** The student's Profile is a tab of My Account now. */
export const Route = createFileRoute("/profile")({
  beforeLoad: () => {
    throw redirect({ to: "/my-account", replace: true });
  },
});
