import { createFileRoute } from "@tanstack/react-router";
import { BranchBatchPage } from "@/features/branch/batch-page";

/** One batch: the step bar, the next action and everything about it. */
export const Route = createFileRoute("/branch/batches/$id")({ component: BranchBatchPage });
