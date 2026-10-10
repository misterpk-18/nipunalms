import { createFileRoute, redirect } from "@tanstack/react-router";

/** Resources are the Files tab of Class Materials now. */
export const Route = createFileRoute("/resources")({
  beforeLoad: () => {
    throw redirect({ to: "/materials", search: { tab: "files" }, replace: true });
  },
});
