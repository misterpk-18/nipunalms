import { createFileRoute } from "@tanstack/react-router";
import { TrainerAssessments } from "@/features/trainer/assessments";

type Tab = "questions" | "tests" | "interviews";

/** Questions, tests and interviews for every batch; `?tab=` picks the tab. */
export const Route = createFileRoute("/admin/assessments")({
  validateSearch: (search: Record<string, unknown>): { tab?: Tab } => {
    const tab = search["tab"];
    return tab === "questions" || tab === "tests" || tab === "interviews" ? { tab } : {};
  },
  component: () => <TrainerAssessments basePath="/admin/assessments" canApprove />,
});
