import { createFileRoute } from "@tanstack/react-router";
import { BranchCompletion } from "@/features/branch/completion";

export const Route = createFileRoute("/branch/completion")({ component: BranchCompletion });
