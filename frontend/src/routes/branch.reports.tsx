import { createFileRoute } from "@tanstack/react-router";
import { Reports } from "@/features/shared/reports";

/** The Branch Manager's Reports: the session's branch. */
export const Route = createFileRoute("/branch/reports")({ component: () => <Reports /> });
