import { createFileRoute } from "@tanstack/react-router";
import { BranchContent } from "@/features/branch/content";

export const Route = createFileRoute("/admin/content-review")({
  component: () => (
    <BranchContent basePath="/admin/content-review" questionsPath="/admin/questions" moreLink={{ to: "/admin/questions", label: "Open Question approvals" }} />
  ),
});
