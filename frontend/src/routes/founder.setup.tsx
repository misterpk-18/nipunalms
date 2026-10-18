import { createFileRoute } from "@tanstack/react-router";
import { AdminSetup } from "@/features/admin/setup";
import { FOUNDER_AREA } from "@/features/shared/central-area";

/** Setup & health, editable: the Founder does what the Super Admin does. */
export const Route = createFileRoute("/founder/setup")({ component: () => <AdminSetup canEdit={FOUNDER_AREA.canEdit} /> });
