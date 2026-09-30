import { createFileRoute } from "@tanstack/react-router";
import { AcademicContentReview } from "@/features/academic/content-review";

export const Route = createFileRoute("/academic/content-review")({ component: AcademicContentReview });
