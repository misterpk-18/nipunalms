import { createFileRoute } from "@tanstack/react-router";
import { AdminDashboard } from "@/features/admin/dashboard";
import { ADMIN_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/admin/")({ component: () => <AdminDashboard canEdit={ADMIN_AREA.canEdit} /> });
