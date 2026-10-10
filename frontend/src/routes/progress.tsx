import { createFileRoute } from "@tanstack/react-router";
import { Progress } from "@/features/student/progress";

/** Overview, Attendance and Results; `?tab=attendance` or `?tab=results` opens one. */
export const Route = createFileRoute("/progress")({
  validateSearch: (search: Record<string, unknown>): { tab?: "attendance" | "results" } =>
    search["tab"] === "attendance" || search["tab"] === "results" ? { tab: search["tab"] } : {},
  component: Progress,
});
