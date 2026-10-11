import { createFileRoute } from "@tanstack/react-router";
import { TrainerRequests } from "@/features/trainer/requests";

export const Route = createFileRoute("/trainer/requests")({ component: TrainerRequests });
