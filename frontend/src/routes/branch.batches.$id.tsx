import { createFileRoute } from "@tanstack/react-router";
import { BatchPage } from "@/features/shared/batch-page";

/** One batch: the step bar, the next action and everything about it. The Branch Manager manages and approves. */
export const Route = createFileRoute("/branch/batches/$id")({
  /** `?tab=requests` opens that section (from the Approvals inbox). */
  validateSearch: (search: Record<string, unknown>): { tab?: string } => (typeof search["tab"] === "string" ? { tab: search["tab"] } : {}),
  component: function BranchBatchRoute() {
    return <BatchPage id={Route.useParams().id} basePath="/branch/batches" manage approve />;
  },
});
