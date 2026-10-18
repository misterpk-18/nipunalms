import { createFileRoute } from "@tanstack/react-router";
import { CoursePage } from "@/features/shared/course-outline/course-page";

/** One course: the CRM's fields read-only and the outline editor. */
export const Route = createFileRoute("/founder/courses/$id")({
  component: function CourseRoute() {
    return <CoursePage id={Route.useParams().id} base="/founder" />;
  },
});
