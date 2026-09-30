import { createFileRoute } from "@tanstack/react-router";
import { Assignments } from "@/features/student/assignments";

export const Route = createFileRoute("/assignments/")({ component: Assignments });
