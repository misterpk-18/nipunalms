import { createFileRoute } from "@tanstack/react-router";
import { Materials } from "@/features/student/materials";

/** Recordings and files in one place; `?tab=files` opens the files. */
export const Route = createFileRoute("/materials")({
  validateSearch: (search: Record<string, unknown>): { tab?: "files" } => (search["tab"] === "files" ? { tab: "files" } : {}),
  component: Materials,
});
