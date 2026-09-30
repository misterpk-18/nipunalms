import { createFileRoute } from "@tanstack/react-router";
import { TrainerToday } from "@/features/trainer/today";

export const Route = createFileRoute("/trainer/")({ component: TrainerToday });
