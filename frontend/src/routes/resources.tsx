import { createFileRoute } from "@tanstack/react-router";
import { Resources } from "@/features/student/resources";

export const Route = createFileRoute("/resources")({ component: Resources });
