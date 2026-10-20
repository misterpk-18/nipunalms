import { createFileRoute } from "@tanstack/react-router";
import { BranchContent } from "@/features/branch/content";

export const Route = createFileRoute("/founder/content-review")({
  component: () => (
    <BranchContent
      basePath="/founder/content-review"
      questionsPath="/founder/questions"
      moreLink={{ to: "/founder/questions", label: "Open Question approvals" }}
    />
  ),
});
