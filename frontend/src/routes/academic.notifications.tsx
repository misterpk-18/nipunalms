import { createFileRoute } from "@tanstack/react-router";
import { NotificationCentre } from "@/features/shared/notification-centre";

export const Route = createFileRoute("/academic/notifications")({ component: () => <NotificationCentre title="Notifications" /> });
