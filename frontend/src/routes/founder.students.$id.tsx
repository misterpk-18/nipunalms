import { createFileRoute } from "@tanstack/react-router";
import { AdminStudentPage } from "@/features/admin/student-page";
import { FOUNDER_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/founder/students/$id")({ component: () => <AdminStudentPage area={FOUNDER_AREA} /> });
