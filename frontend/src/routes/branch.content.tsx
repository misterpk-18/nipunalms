import { createFileRoute } from "@tanstack/react-router";
import { BranchContent } from "@/features/branch/content";

export const Route = createFileRoute("/branch/content")({ component: BranchContent });
