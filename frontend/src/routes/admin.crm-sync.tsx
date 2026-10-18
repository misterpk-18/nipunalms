import { createFileRoute } from "@tanstack/react-router";
import { AdminCrmSync } from "@/features/admin/crm-sync";
import { ADMIN_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/admin/crm-sync")({ component: () => <AdminCrmSync canEdit={ADMIN_AREA.canEdit} /> });
