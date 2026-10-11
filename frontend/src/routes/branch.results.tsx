import { createFileRoute } from "@tanstack/react-router";
import { BranchResults } from "@/features/branch/results";

export const Route = createFileRoute("/branch/results")({ component: BranchResults });
