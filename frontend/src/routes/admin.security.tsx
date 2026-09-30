import { createFileRoute } from "@tanstack/react-router";
import { AdminSecurity } from "@/features/admin/security";

export const Route = createFileRoute("/admin/security")({ component: AdminSecurity });
