import { createFileRoute } from "@tanstack/react-router";
import { BranchIssues } from "@/features/shared/issues";

export const Route = createFileRoute("/branch/issues")({ component: BranchIssues });
