import { createFileRoute } from "@tanstack/react-router";
import { AttendanceOverview } from "@/features/shared/attendance-overview";
import { ADMIN_AREA } from "@/features/shared/central-area";

export const Route = createFileRoute("/admin/attendance")({ component: () => <AttendanceOverview area={ADMIN_AREA} /> });
