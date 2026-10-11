import { createFileRoute } from "@tanstack/react-router";
import { GradeScreen } from "@/features/trainer/grade-screen";

/** One hand-in (`submission`) or test attempt (`attempt`) on the focused grading screen; `?batch=<id>` keeps the inbox filter for "Save & next". */
export const Route = createFileRoute("/trainer/to-grade/$kind/$id")({
  validateSearch: (search: Record<string, unknown>): { batch?: number } => (Number(search["batch"]) > 0 ? { batch: Number(search["batch"]) } : {}),
  component: GradeScreen,
});
