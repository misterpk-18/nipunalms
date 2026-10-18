import { createFileRoute } from "@tanstack/react-router";
import { AdminUsers } from "@/features/admin/users";
import { ADMIN_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/admin/users")({ component: () => <AdminUsers canEdit={ADMIN_AREA.canEdit} /> });
