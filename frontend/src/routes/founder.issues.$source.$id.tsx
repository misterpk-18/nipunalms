import { createFileRoute } from "@tanstack/react-router";
import { IssueDetail } from "@/features/shared/issues";

/** Read-only issue detail with Assign: where "Go fix it" leads for branch work (decision 19). */
export const Route = createFileRoute("/founder/issues/$source/$id")({
  component: function IssueRoute() {
    const { source, id } = Route.useParams();
    return <IssueDetail source={source} sourceId={Number(id)} listPath="/founder/issues" />;
  },
});
