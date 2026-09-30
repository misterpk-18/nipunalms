import { createFileRoute } from "@tanstack/react-router";
import { AcademicExceptions } from "@/features/academic/exceptions";

export const Route = createFileRoute("/academic/exceptions")({ component: AcademicExceptions });
