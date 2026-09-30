import { createFileRoute } from "@tanstack/react-router";
import { BranchDashboard } from "@/features/branch/dashboard";

export const Route = createFileRoute("/branch/")({ component: BranchDashboard });
