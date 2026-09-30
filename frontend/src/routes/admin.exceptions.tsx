import { createFileRoute } from "@tanstack/react-router";
import { AdminExceptions } from "@/features/admin/exceptions";

export const Route = createFileRoute("/admin/exceptions")({ component: AdminExceptions });
