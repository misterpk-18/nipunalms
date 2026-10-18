import { createFileRoute } from "@tanstack/react-router";
import { AdminStudentPage } from "@/features/admin/student-page";
import { ADMIN_AREA } from "@/features/shared/central-area";

/** One student's account: who they are, what to do next, and everything the Super Admin can do to it. */
export const Route = createFileRoute("/admin/students/$id")({ component: () => <AdminStudentPage area={ADMIN_AREA} /> });
