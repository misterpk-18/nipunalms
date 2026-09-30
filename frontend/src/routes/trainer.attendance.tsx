import { createFileRoute } from "@tanstack/react-router";
import { TrainerAttendance } from "@/features/trainer/attendance";

export const Route = createFileRoute("/trainer/attendance")({ component: TrainerAttendance });
