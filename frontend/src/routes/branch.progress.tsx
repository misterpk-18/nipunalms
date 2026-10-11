import { createFileRoute } from "@tanstack/react-router";
import { BranchAttendance } from "@/features/branch/attendance";

export const Route = createFileRoute("/branch/progress")({ component: BranchAttendance });
