import { createFileRoute } from "@tanstack/react-router";
import { AdminAudit } from "@/features/admin/audit";
import { ADMIN_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/admin/audit")({ component: () => <AdminAudit area={ADMIN_AREA} /> });
