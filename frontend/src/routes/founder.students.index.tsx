import { createFileRoute } from "@tanstack/react-router";
import { AdminStudents } from "@/features/admin/students";
import { FOUNDER_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/founder/students/")({ component: () => <AdminStudents area={FOUNDER_AREA} /> });
