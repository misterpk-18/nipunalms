import { createFileRoute } from "@tanstack/react-router";
import { TrainerNotifications } from "@/features/trainer/notifications";

export const Route = createFileRoute("/trainer/notifications")({ component: TrainerNotifications });
