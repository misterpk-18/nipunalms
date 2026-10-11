import { createFileRoute } from "@tanstack/react-router";
import { TrainerAttendance } from "@/features/trainer/attendance";

/** The Unmarked & corrections list; `?session=<id>` opens that class's register. */
export const Route = createFileRoute("/trainer/attendance")({
  validateSearch: (search: Record<string, unknown>): { session?: number } => (Number(search["session"]) > 0 ? { session: Number(search["session"]) } : {}),
  component: TrainerAttendance,
});
