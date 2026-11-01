import { createFileRoute } from "@tanstack/react-router";
import { BatchPage } from "@/features/shared/batch-page";

/** One batch: the step bar, the next action and everything about it. The Founder and Super Admin manage it as a Branch Manager does. */
export const Route = createFileRoute("/founder/batches/$id")({
  component: function BatchRoute() {
    return <BatchPage id={Route.useParams().id} basePath="/founder/batches" manage approve />;
  },
});
