import { createFileRoute } from "@tanstack/react-router";
import { AdminIntegrations } from "@/features/admin/integrations";

export const Route = createFileRoute("/admin/integrations")({ component: AdminIntegrations });
