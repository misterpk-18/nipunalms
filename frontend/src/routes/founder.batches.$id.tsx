import { createFileRoute } from "@tanstack/react-router";
import { BatchPage } from "@/features/branch/batch-page";

/** One batch, read-only. */
export const Route = createFileRoute("/founder/batches/$id")({
  component: function BatchRoute() {
    return <BatchPage id={Route.useParams().id} basePath="/founder/batches" manage={false} approve={false} />;
  },
});
