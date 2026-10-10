import { createFileRoute } from "@tanstack/react-router";
import { MeetOperations } from "@/features/academic/meet-operations";

export const Route = createFileRoute("/branch/meet-operations")({ component: MeetOperations });
