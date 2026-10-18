import { createFileRoute } from "@tanstack/react-router";
import { CrossBranchIssues } from "@/features/shared/issues";

export const Route = createFileRoute("/founder/issues/")({ component: CrossBranchIssues });
