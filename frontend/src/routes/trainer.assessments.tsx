import { createFileRoute, redirect } from "@tanstack/react-router";
import { TrainerAssessments } from "@/features/trainer/assessments";

type Tab = "questions" | "tests" | "interviews";

/** `?tab=` picks the tab. The old `?tab=grading` link (the grading queue moved to To grade) still lands in the right place. */
export const Route = createFileRoute("/trainer/assessments")({
  validateSearch: (search: Record<string, unknown>): { tab?: Tab | "grading" } => {
    const tab = search["tab"];
    return tab === "questions" || tab === "tests" || tab === "interviews" || tab === "grading" ? { tab } : {};
  },
  beforeLoad: ({ search }) => {
    if (search.tab === "grading") throw redirect({ to: "/trainer/to-grade", replace: true });
  },
  component: TrainerAssessments,
});
