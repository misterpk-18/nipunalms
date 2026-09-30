import { createFileRoute } from "@tanstack/react-router";
import { AcademicProgress } from "@/features/academic/progress";

export const Route = createFileRoute("/academic/progress")({ component: AcademicProgress });
