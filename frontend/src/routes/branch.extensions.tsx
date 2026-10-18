import { createFileRoute } from "@tanstack/react-router";
import { BranchExtensions } from "@/features/branch/extensions-page";

export const Route = createFileRoute("/branch/extensions")({ component: BranchExtensions });
