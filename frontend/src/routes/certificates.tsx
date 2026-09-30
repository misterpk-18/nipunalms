import { createFileRoute } from "@tanstack/react-router";
import { Certificates } from "@/features/student/certificates";

export const Route = createFileRoute("/certificates")({ component: Certificates });
