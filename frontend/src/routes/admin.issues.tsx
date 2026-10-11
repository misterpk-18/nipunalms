import { createFileRoute } from "@tanstack/react-router";
import { AdminIssues } from "@/features/admin/issues";

export const Route = createFileRoute("/admin/issues")({ component: AdminIssues });
