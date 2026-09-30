import { createFileRoute } from "@tanstack/react-router";
import { BranchRequests } from "@/features/branch/requests";

export const Route = createFileRoute("/branch/requests")({ component: BranchRequests });
