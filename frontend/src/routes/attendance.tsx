import { createFileRoute } from "@tanstack/react-router";
import { Attendance } from "@/features/student/attendance";

export const Route = createFileRoute("/attendance")({ component: Attendance });
