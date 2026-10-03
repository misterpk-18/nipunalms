import { createFileRoute } from "@tanstack/react-router";
import { MeetOperations } from "@/features/academic/meet-operations";

// The Branch Manager confirms batches and decides the requests on the same screens the coordinator prepares them on
export const Route = createFileRoute("/branch/meet-operations")({ component: MeetOperations });
