import { createFileRoute } from "@tanstack/react-router";
import { TrainerStudents } from "@/features/trainer/students";

/** `?batch=<id>` narrows the list to one batch (the batch pages link here). */
export const Route = createFileRoute("/trainer/students/")({
  validateSearch: (search: Record<string, unknown>): { batch?: number } => (Number(search["batch"]) > 0 ? { batch: Number(search["batch"]) } : {}),
  component: TrainerStudents,
});
