import { createFileRoute } from "@tanstack/react-router";
import { NotificationCentre } from "@/features/shared/notification-centre";

export const Route = createFileRoute("/branch/notifications")({ component: () => <NotificationCentre title="Notifications" /> });
