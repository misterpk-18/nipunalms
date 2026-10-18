import { createFileRoute } from "@tanstack/react-router";
import { AdminUsers } from "@/features/admin/users";
import { FOUNDER_AREA } from "@/features/shared/central-area";

/** Users & access with the hand-out section: the same page as the Super Admin's, read-write. */
export const Route = createFileRoute("/founder/users")({ component: () => <AdminUsers canEdit={FOUNDER_AREA.canEdit} /> });
