import { createFileRoute } from "@tanstack/react-router";
import { TrainerSupport } from "@/features/trainer/support";

export const Route = createFileRoute("/trainer/support")({ component: TrainerSupport });
