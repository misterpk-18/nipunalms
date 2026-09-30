import { createFileRoute } from "@tanstack/react-router";
import { Progress } from "@/features/student/progress";

export const Route = createFileRoute("/progress")({ component: Progress });
