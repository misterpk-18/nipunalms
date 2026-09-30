import { createFileRoute } from "@tanstack/react-router";
import { CourseDetail } from "@/features/student/course-detail";

export const Route = createFileRoute("/courses/$enrolmentId")({ component: CourseDetail });
