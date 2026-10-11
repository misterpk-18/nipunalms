import { createFileRoute } from "@tanstack/react-router";
import { TrainerBatchPage } from "@/features/trainer/batch-page";

/** One batch: classes, students, assignments, content and progress. */
export const Route = createFileRoute("/trainer/batches/$id")({ component: TrainerBatchPage });
