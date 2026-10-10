import { createFileRoute } from "@tanstack/react-router";
import { AcademicCurriculum } from "@/features/academic/curriculum";

export const Route = createFileRoute("/branch/curriculum")({ component: AcademicCurriculum });
