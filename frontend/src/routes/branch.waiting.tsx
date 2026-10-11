import { createFileRoute } from "@tanstack/react-router";
import { BranchWaiting } from "@/features/branch/waiting";

export const Route = createFileRoute("/branch/waiting")({ component: BranchWaiting });
