import { createFileRoute } from "@tanstack/react-router";
import { Results } from "@/features/student/results";

export const Route = createFileRoute("/results")({ component: Results });
