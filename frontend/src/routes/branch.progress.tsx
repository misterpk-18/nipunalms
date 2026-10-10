import { createFileRoute } from "@tanstack/react-router";
import { AcademicProgress } from "@/features/academic/progress";

export const Route = createFileRoute("/branch/progress")({ component: AcademicProgress });
