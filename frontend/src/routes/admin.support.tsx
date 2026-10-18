import { createFileRoute } from "@tanstack/react-router";
import { SupportOverview } from "@/features/shared/support-overview";

export const Route = createFileRoute("/admin/support")({ component: SupportOverview });
