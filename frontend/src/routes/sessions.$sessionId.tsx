import { createFileRoute } from "@tanstack/react-router";
import { SessionDetail } from "@/features/student/session-detail";

export const Route = createFileRoute("/sessions/$sessionId")({ component: SessionDetail });
