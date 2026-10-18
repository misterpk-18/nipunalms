import { createFileRoute } from "@tanstack/react-router";
import { AdminSetup } from "@/features/admin/setup";
import { ADMIN_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/admin/setup")({ component: () => <AdminSetup canEdit={ADMIN_AREA.canEdit} /> });
