import { createFileRoute } from "@tanstack/react-router";
import { Career } from "@/features/student/career";

export const Route = createFileRoute("/career")({ component: Career });
