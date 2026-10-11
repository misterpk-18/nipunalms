import { createFileRoute } from "@tanstack/react-router";
import { TrainerAssessments } from "@/features/trainer/assessments";

/** `?tab=grading` opens the grading queue (the Today to-do links to it). */
export const Route = createFileRoute("/trainer/assessments")({
  validateSearch: (search: Record<string, unknown>): { tab?: "grading" } => (search["tab"] === "grading" ? { tab: "grading" } : {}),
  component: TrainerAssessments,
});
