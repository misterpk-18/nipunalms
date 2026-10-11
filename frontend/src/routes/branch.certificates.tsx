import { createFileRoute, redirect } from "@tanstack/react-router";

/** Certificate Eligibility and Completion Review became Completion & certificates (UX phase U15). */
export const Route = createFileRoute("/branch/certificates")({
  beforeLoad: () => {
    throw redirect({ href: "/branch/completion?stage=completed", replace: true });
  },
});
