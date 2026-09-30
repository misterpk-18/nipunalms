import { createFileRoute } from "@tanstack/react-router";
import { TrainerReports } from "@/features/trainer/reports";

export const Route = createFileRoute("/trainer/reports")({ component: TrainerReports });
