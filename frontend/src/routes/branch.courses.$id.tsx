import { createFileRoute } from "@tanstack/react-router";
import { CoursePage } from "@/features/shared/course-outline/course-page";

/** One course's outline, read-only, with "New batch for this course". */
export const Route = createFileRoute("/branch/courses/$id")({
  component: function CourseRoute() {
    return <CoursePage id={Route.useParams().id} base="/branch" />;
  },
});
