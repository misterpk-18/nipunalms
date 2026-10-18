import { createFileRoute } from "@tanstack/react-router";
import { AdminStudents } from "@/features/admin/students";
import { ADMIN_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/admin/students/")({ component: () => <AdminStudents area={ADMIN_AREA} /> });
