import { createFileRoute } from "@tanstack/react-router";
import { AdminCrmSync } from "@/features/admin/crm-sync";
import { FOUNDER_AREA } from "@/features/shared/central-area";

/** What the CRM sent and what failed, with Retry: the Founder does what the Super Admin does. */
export const Route = createFileRoute("/founder/crm-sync")({ component: () => <AdminCrmSync canEdit={FOUNDER_AREA.canEdit} /> });
