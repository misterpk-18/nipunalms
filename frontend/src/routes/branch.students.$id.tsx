import { createFileRoute } from "@tanstack/react-router";
import { BranchStudentPage } from "@/features/branch/student-page";

/** One student at this branch, read-only (no account actions: those are the Super Admin's and Founder's). */
export const Route = createFileRoute("/branch/students/$id")({ component: BranchStudentPage });
