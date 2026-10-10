import { createFileRoute } from "@tanstack/react-router";
import { AcademicRecordingExceptions } from "@/features/academic/recording-exceptions";

export const Route = createFileRoute("/branch/recording-exceptions")({ component: AcademicRecordingExceptions });
