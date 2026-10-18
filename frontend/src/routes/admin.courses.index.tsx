import { createFileRoute } from "@tanstack/react-router";
import { CourseList } from "@/features/shared/course-outline/course-list";

/** Every course with what is running in each branch; open one to edit its outline. */
export const Route = createFileRoute("/admin/courses/")({ component: () => <CourseList base="/admin" /> });
