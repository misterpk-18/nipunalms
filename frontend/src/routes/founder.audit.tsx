import { createFileRoute } from "@tanstack/react-router";
import { AdminAudit } from "@/features/admin/audit";
import { FOUNDER_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/founder/audit")({ component: () => <AdminAudit area={FOUNDER_AREA} /> });
