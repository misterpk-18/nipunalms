import { createFileRoute } from "@tanstack/react-router";
import { Tests } from "@/features/student/tests";

export const Route = createFileRoute("/tests/")({ component: Tests });
