import { createFileRoute } from "@tanstack/react-router";
import { AdminStudents } from "@/features/admin/students";

export const Route = createFileRoute("/admin/students")({ component: AdminStudents });
