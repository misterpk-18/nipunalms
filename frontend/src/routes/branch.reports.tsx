import { createFileRoute } from "@tanstack/react-router";
import { BranchReports } from "@/features/branch/reports";

export const Route = createFileRoute("/branch/reports")({ component: BranchReports });
