import { createFileRoute } from "@tanstack/react-router";
import { AcademicSchedule } from "@/features/academic/schedule";

export const Route = createFileRoute("/academic/schedule")({ component: AcademicSchedule });
