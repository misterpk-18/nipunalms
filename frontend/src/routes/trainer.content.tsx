import { createFileRoute } from "@tanstack/react-router";
import { TrainerContent } from "@/features/trainer/content";

export const Route = createFileRoute("/trainer/content")({ component: TrainerContent });
