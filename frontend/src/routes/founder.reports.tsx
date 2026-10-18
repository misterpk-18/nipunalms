import { createFileRoute } from "@tanstack/react-router";
import { FOUNDER_AREA } from "@/features/shared/central-area";
import { Reports } from "@/features/shared/reports";

/** Company-wide Reports for all branches or one (branch filter). */
export const Route = createFileRoute("/founder/reports")({ component: () => <Reports area={FOUNDER_AREA} /> });
