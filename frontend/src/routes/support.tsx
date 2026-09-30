import { createFileRoute } from "@tanstack/react-router";
import { Support } from "@/features/student/support";

export const Route = createFileRoute("/support")({ component: Support });
