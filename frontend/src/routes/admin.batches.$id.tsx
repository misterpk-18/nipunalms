import { createFileRoute } from "@tanstack/react-router";
import { BatchPage } from "@/features/shared/batch-page";

/** One batch: the step bar, the next action and everything about it. The Super Admin and Founder manage it as a Branch Manager does. */
export const Route = createFileRoute("/admin/batches/$id")({
  /** `?tab=requests` opens that section (from the Approvals inbox). */
  validateSearch: (search: Record<string, unknown>): { tab?: string } => (typeof search["tab"] === "string" ? { tab: search["tab"] } : {}),
  component: function BatchRoute() {
    return <BatchPage id={Route.useParams().id} basePath="/admin/batches" manage approve />;
  },
});
