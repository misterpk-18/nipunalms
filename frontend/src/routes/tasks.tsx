import { createFileRoute } from "@tanstack/react-router";
import { Tasks } from "@/features/student/tasks";

export const Route = createFileRoute("/tasks")({ component: Tasks });
