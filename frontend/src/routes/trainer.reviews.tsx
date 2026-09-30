import { createFileRoute } from "@tanstack/react-router";
import { TrainerReviews } from "@/features/trainer/reviews";

export const Route = createFileRoute("/trainer/reviews")({ component: TrainerReviews });
