import { createFileRoute } from "@tanstack/react-router";
import { SupportRequestPage } from "@/features/student/support-request";

export const Route = createFileRoute("/support/$requestId")({ component: SupportRequestPage });
