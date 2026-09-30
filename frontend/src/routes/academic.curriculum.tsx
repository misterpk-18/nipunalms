import { createFileRoute } from "@tanstack/react-router";
import { AcademicCurriculum } from "@/features/academic/curriculum";

export const Route = createFileRoute("/academic/curriculum")({ component: AcademicCurriculum });
