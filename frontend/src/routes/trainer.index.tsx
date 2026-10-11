import { createFileRoute } from "@tanstack/react-router";
import { TrainerToday } from "@/features/trainer/today";

/** Today; `?session=<id>` runs that class's flow (Run class, or a class that still needs its log). */
export const Route = createFileRoute("/trainer/")({
  validateSearch: (search: Record<string, unknown>): { session?: number } => (Number(search["session"]) > 0 ? { session: Number(search["session"]) } : {}),
  component: TrainerToday,
});
