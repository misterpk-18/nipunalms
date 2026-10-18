import { createFileRoute } from "@tanstack/react-router";
import { AiControlsPage } from "@/features/shared/ai-controls";

/** The Founder switches AI off and restores it here, the same page the Super Admin uses. */
export const Route = createFileRoute("/founder/ai-controls")({ component: AiControlsPage });
