import { createFileRoute, redirect } from "@tanstack/react-router";

/** Recordings are part of Class Materials now. */
export const Route = createFileRoute("/recordings")({
  beforeLoad: () => {
    throw redirect({ to: "/materials", replace: true });
  },
});
