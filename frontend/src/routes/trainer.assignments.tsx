import { createFileRoute } from "@tanstack/react-router";
import { TrainerAssignments } from "@/features/trainer/assignments";

export const Route = createFileRoute("/trainer/assignments")({ component: TrainerAssignments });
