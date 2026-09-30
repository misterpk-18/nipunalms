import { createFileRoute } from "@tanstack/react-router";
import { Recordings } from "@/features/student/recordings";

export const Route = createFileRoute("/recordings")({ component: Recordings });
