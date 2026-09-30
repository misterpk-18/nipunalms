import { createFileRoute } from "@tanstack/react-router";
import { TrackDetail } from "@/features/student/track-detail";

export const Route = createFileRoute("/courses/$enrolmentId_/tracks/$trackId")({ component: TrackDetail });
