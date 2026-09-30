import { createFileRoute } from "@tanstack/react-router";
import { AcademicAssessments } from "@/features/academic/assessments";

export const Route = createFileRoute("/academic/assessments")({ component: AcademicAssessments });
