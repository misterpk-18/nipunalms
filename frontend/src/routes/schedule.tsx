import { createFileRoute } from "@tanstack/react-router";
import { Schedule } from "@/features/student/schedule";

export const Route = createFileRoute("/schedule")({ component: Schedule });
