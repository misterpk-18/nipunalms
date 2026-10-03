import { createFileRoute } from "@tanstack/react-router";
import { FounderCurriculum } from "@/features/founder/curriculum";

export const Route = createFileRoute("/founder/curriculum")({ component: FounderCurriculum });
