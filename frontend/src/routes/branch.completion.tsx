import { createFileRoute } from "@tanstack/react-router";
import { AcademicCompletion } from "@/features/academic/completion";

export const Route = createFileRoute("/branch/completion")({ component: AcademicCompletion });
