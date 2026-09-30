import { createFileRoute } from "@tanstack/react-router";
import { TrainerAssessments } from "@/features/trainer/assessments";

export const Route = createFileRoute("/trainer/assessments")({ component: TrainerAssessments });
