import { createFileRoute } from "@tanstack/react-router";
import { TrainerBatches } from "@/features/trainer/batches";

export const Route = createFileRoute("/trainer/batches")({ component: TrainerBatches });
