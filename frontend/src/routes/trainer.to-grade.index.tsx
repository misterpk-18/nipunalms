import { createFileRoute } from "@tanstack/react-router";
import { TrainerToGrade } from "@/features/trainer/to-grade";

/** The To grade inbox; `?batch=<id>` narrows it to one batch. */
export const Route = createFileRoute("/trainer/to-grade/")({
  validateSearch: (search: Record<string, unknown>): { batch?: number } => (Number(search["batch"]) > 0 ? { batch: Number(search["batch"]) } : {}),
  component: TrainerToGrade,
});
