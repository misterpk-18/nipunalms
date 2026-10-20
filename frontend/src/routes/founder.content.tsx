import { createFileRoute } from "@tanstack/react-router";
import { TrainerContent } from "@/features/trainer/content";

export const Route = createFileRoute("/founder/content")({
  component: () => <TrainerContent basePath="/founder/content" reviewPath="/founder/content-review" />,
});
