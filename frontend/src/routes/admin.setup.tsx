import { createFileRoute } from "@tanstack/react-router";
import { AdminSetup } from "@/features/admin/setup";

export const Route = createFileRoute("/admin/setup")({ component: AdminSetup });
