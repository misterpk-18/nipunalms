import { createFileRoute } from "@tanstack/react-router";
import { TrainerContent } from "@/features/trainer/content";

/** `?batch=<id>` shows only that batch's content (the batch page links here). */
export const Route = createFileRoute("/trainer/content")({
  validateSearch: (search: Record<string, unknown>): { batch?: number } => (Number(search["batch"]) > 0 ? { batch: Number(search["batch"]) } : {}),
  component: TrainerContent,
});
