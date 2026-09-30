import { createFileRoute } from "@tanstack/react-router";
import { FounderDashboard } from "@/features/founder/dashboard";

export const Route = createFileRoute("/founder")({ component: FounderDashboard });
