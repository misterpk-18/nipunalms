import { createFileRoute } from "@tanstack/react-router";
import { Finance } from "@/features/student/finance";

export const Route = createFileRoute("/finance")({ component: Finance });
