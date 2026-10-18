import { createFileRoute } from "@tanstack/react-router";
import { AcademicCalendar, CALENDAR_READ_ONLY } from "@/features/shared/academic-calendar";

/** Holidays and closures, read-only, so a trainer can plan around them. Branch Managers propose and Super Admin / Founder decide. */
export const Route = createFileRoute("/trainer/calendar")({ component: () => <AcademicCalendar config={CALENDAR_READ_ONLY} /> });
