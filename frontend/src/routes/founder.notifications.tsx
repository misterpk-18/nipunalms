import { createFileRoute } from "@tanstack/react-router";
import { NotificationCentre } from "@/features/shared/notification-centre";

export const Route = createFileRoute("/founder/notifications")({ component: () => <NotificationCentre title="Notifications" showSystemIssuesTab /> });
