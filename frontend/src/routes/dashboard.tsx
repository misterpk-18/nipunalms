import { createFileRoute } from "@tanstack/react-router";
import { StudentHome } from "@/features/student/dashboard";

export const Route = createFileRoute("/dashboard")({ component: StudentHome });
