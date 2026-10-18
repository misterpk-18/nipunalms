import { createFileRoute } from "@tanstack/react-router";
import { BranchWaiting } from "@/features/branch/waiting";

export const Route = createFileRoute("/branch/waiting")({
  validateSearch: (search: Record<string, unknown>): { q?: string } => ({
    ...(typeof search["q"] === "string" && search["q"].trim() ? { q: search["q"].trim() } : {}),
  }),
  component: () => <BranchWaiting manage />,
});
