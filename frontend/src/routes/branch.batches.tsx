import { createFileRoute } from "@tanstack/react-router";
import { AcademicBatches } from "@/features/academic/batches";

// The Branch Manager confirms batches and decides the requests on the same screens the coordinator prepares them on
export const Route = createFileRoute("/branch/batches")({ component: AcademicBatches });
