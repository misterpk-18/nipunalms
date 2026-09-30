import { createFileRoute } from "@tanstack/react-router";
import { Notifications } from "@/features/student/notifications";

export const Route = createFileRoute("/notifications")({ component: Notifications });
