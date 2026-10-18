import { createFileRoute } from "@tanstack/react-router";
import { AttendanceOverview } from "@/features/shared/attendance-overview";
import { FOUNDER_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/founder/attendance")({ component: () => <AttendanceOverview area={FOUNDER_AREA} /> });
