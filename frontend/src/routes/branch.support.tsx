import { createFileRoute } from "@tanstack/react-router";
import { BranchSupport } from "@/features/branch/support";

export const Route = createFileRoute("/branch/support")({ component: BranchSupport });
