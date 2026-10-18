import { createFileRoute } from "@tanstack/react-router";
import { BatchPage } from "@/features/shared/batch-page";

/** One batch, read-only. */
export const Route = createFileRoute("/admin/batches/$id")({
  component: function BatchRoute() {
    return <BatchPage id={Route.useParams().id} basePath="/admin/batches" manage={false} approve={false} />;
  },
});
