import { createFileRoute } from "@tanstack/react-router";
import { BranchOperations } from "@/features/branch/operations";

export const Route = createFileRoute("/branch/operations")({ component: BranchOperations });
