import { createFileRoute } from "@tanstack/react-router";
import { AdminCrmSync } from "@/features/admin/crm-sync";

export const Route = createFileRoute("/admin/crm-sync")({ component: AdminCrmSync });
