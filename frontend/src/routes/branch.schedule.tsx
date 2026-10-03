import { createFileRoute } from "@tanstack/react-router";
import { AcademicSchedule } from "@/features/academic/schedule";

// The Branch Manager confirms batches and decides the requests on the same screens the coordinator prepares them on
export const Route = createFileRoute("/branch/schedule")({ component: AcademicSchedule });
