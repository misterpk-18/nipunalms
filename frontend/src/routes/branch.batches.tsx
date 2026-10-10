import { createFileRoute } from "@tanstack/react-router";
import { AcademicBatches } from "@/features/academic/batches";

export const Route = createFileRoute("/branch/batches")({ component: AcademicBatches });
