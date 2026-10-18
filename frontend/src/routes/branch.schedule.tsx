import { createFileRoute } from "@tanstack/react-router";
import { BranchSchedule } from "@/features/branch/schedule";

type Search = { view?: "week" | "list"; by?: "batch" | "trainer"; week?: string; batch?: number; decide?: 1 };

/** `?view=list`, `?by=trainer`, `?week=<Monday>`, `?batch=<id>`; `?decide=1` scrolls to what needs a decision. */
export const Route = createFileRoute("/branch/schedule")({
  validateSearch: (search: Record<string, unknown>): Search => ({
    ...(search["view"] === "list" || search["view"] === "week" ? { view: search["view"] } : {}),
    ...(search["by"] === "trainer" || search["by"] === "batch" ? { by: search["by"] } : {}),
    ...(typeof search["week"] === "string" && /^\d{4}-\d{2}-\d{2}$/.test(search["week"]) ? { week: search["week"] } : {}),
    ...(Number(search["batch"]) > 0 ? { batch: Number(search["batch"]) } : {}),
    ...(Number(search["decide"]) === 1 ? { decide: 1 as const } : {}),
  }),
  component: () => <BranchSchedule manage approve />,
});
