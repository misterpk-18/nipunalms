import { createFileRoute, redirect } from "@tanstack/react-router";

/** "Reviews" became "To grade" (UX phase U13); old links and bookmarks still work. */
export const Route = createFileRoute("/trainer/reviews")({
  beforeLoad: () => {
    throw redirect({ to: "/trainer/to-grade", replace: true });
  },
});
