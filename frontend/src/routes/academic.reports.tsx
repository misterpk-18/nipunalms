import { createFileRoute } from "@tanstack/react-router";
import { AcademicReports } from "@/features/academic/reports";

export const Route = createFileRoute("/academic/reports")({ component: AcademicReports });
