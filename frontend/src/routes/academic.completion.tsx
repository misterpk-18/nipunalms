import { createFileRoute } from "@tanstack/react-router";
import { AcademicCompletion } from "@/features/academic/completion";

export const Route = createFileRoute("/academic/completion")({ component: AcademicCompletion });
