import { createFileRoute } from "@tanstack/react-router";
import { TrainerCompletion } from "@/features/trainer/completion";

export const Route = createFileRoute("/trainer/completion")({ component: TrainerCompletion });
