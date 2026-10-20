import { createFileRoute } from "@tanstack/react-router";
import { TrainerContent } from "@/features/trainer/content";

export const Route = createFileRoute("/admin/content")({ component: () => <TrainerContent basePath="/admin/content" reviewPath="/admin/content-review" /> });
