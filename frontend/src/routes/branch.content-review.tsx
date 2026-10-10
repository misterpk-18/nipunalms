import { createFileRoute } from "@tanstack/react-router";
import { AcademicContentReview } from "@/features/academic/content-review";

export const Route = createFileRoute("/branch/content-review")({ component: AcademicContentReview });
