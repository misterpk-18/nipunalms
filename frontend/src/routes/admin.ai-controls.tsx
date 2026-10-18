import { createFileRoute } from "@tanstack/react-router";
import { AiControlsPage } from "@/features/shared/ai-controls";

export const Route = createFileRoute("/admin/ai-controls")({ component: AiControlsPage });
