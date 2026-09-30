import { createFileRoute } from "@tanstack/react-router";
import { TrainerSessions } from "@/features/trainer/sessions";

export const Route = createFileRoute("/trainer/sessions")({ component: TrainerSessions });
