import { createFileRoute } from "@tanstack/react-router";
import { AcademicDashboard } from "@/features/academic/dashboard";

export const Route = createFileRoute("/academic/")({ component: AcademicDashboard });
