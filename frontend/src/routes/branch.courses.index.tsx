import { createFileRoute } from "@tanstack/react-router";
import { CourseList } from "@/features/shared/course-outline/course-list";

/** The courses on offer, read-only. */
export const Route = createFileRoute("/branch/courses/")({ component: () => <CourseList base="/branch" /> });
