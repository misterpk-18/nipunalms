import { createFileRoute } from "@tanstack/react-router";
import { AssignmentDetail } from "@/features/student/assignment-detail";

export const Route = createFileRoute("/assignments/$id")({ component: AssignmentDetail });
