import { createFileRoute, redirect } from "@tanstack/react-router";

// The Academic Coordinator workspace was merged into the Branch Manager's: old links and bookmarks land on the Branch dashboard
export const Route = createFileRoute("/academic/")({
  beforeLoad: () => {
    throw redirect({ href: "/branch", replace: true });
  },
});
