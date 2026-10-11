import { createFileRoute } from "@tanstack/react-router";
import { BranchRecordings } from "@/features/branch/recordings";

export const Route = createFileRoute("/branch/recordings")({ component: BranchRecordings });
