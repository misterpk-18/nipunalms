import { createFileRoute } from "@tanstack/react-router";
import { ADMIN_AREA } from "@/features/shared/central-area";
import { Reports } from "@/features/shared/reports";

/** Reports for all branches or one (branch filter). */
export const Route = createFileRoute("/admin/reports")({ component: () => <Reports area={ADMIN_AREA} /> });
