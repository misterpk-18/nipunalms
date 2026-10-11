import { createFileRoute } from "@tanstack/react-router";
import { BranchBatches } from "@/features/branch/batches";

/** `?new=1` opens the New batch steps (`&course=<id>` starts with that course). */
export const Route = createFileRoute("/branch/batches/")({
  validateSearch: (search: Record<string, unknown>): { new?: 1; course?: number } => ({
    ...(Number(search["new"]) === 1 ? { new: 1 as const } : {}),
    ...(Number(search["course"]) > 0 ? { course: Number(search["course"]) } : {}),
  }),
  component: BranchBatches,
});
