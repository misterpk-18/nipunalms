import { createFileRoute } from "@tanstack/react-router";
import { AcademicCalendar, CALENDAR_CENTRAL } from "@/features/shared/academic-calendar";

export const Route = createFileRoute("/admin/calendar")({ component: () => <AcademicCalendar config={CALENDAR_CENTRAL} /> });
