import { createFileRoute } from "@tanstack/react-router";
import { AdminCalendar } from "@/features/admin/calendar";

export const Route = createFileRoute("/admin/calendar")({ component: AdminCalendar });
