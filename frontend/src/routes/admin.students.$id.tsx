import { createFileRoute } from "@tanstack/react-router";
import { AdminStudentPage } from "@/features/admin/student-page";

/** One student's account: who they are, what to do next, and everything the Super Admin can do to it. */
export const Route = createFileRoute("/admin/students/$id")({ component: AdminStudentPage });
