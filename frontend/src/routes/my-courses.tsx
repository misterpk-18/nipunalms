import { createFileRoute } from "@tanstack/react-router";
import { MyCourses } from "@/features/student/my-courses";

export const Route = createFileRoute("/my-courses")({ component: MyCourses });
