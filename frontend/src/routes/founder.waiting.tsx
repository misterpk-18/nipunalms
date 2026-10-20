import { createFileRoute } from "@tanstack/react-router";
import { BranchWaiting } from "@/features/branch/waiting";

/** Every branch's students waiting for a batch; the Founder can allocate them (the one branch action they share with Branch Managers). */
export const Route = createFileRoute("/founder/waiting")({
  validateSearch: (search: Record<string, unknown>): { q?: string } => ({
    ...(typeof search["q"] === "string" && search["q"].trim() ? { q: search["q"].trim() } : {}),
  }),
  component: () => <BranchWaiting manage basePath="/founder/batches" />,
});
