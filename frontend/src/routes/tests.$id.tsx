import { createFileRoute } from "@tanstack/react-router";
import { TestDetail } from "@/features/student/test-detail";

export const Route = createFileRoute("/tests/$id")({ component: TestDetail });
