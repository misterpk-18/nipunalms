import { createFileRoute } from "@tanstack/react-router";
import { TopicDetail } from "@/features/student/topic-detail";

export const Route = createFileRoute("/topics/$topicId")({ component: TopicDetail });
