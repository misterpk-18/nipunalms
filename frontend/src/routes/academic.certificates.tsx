import { createFileRoute } from "@tanstack/react-router";
import { AcademicCertificates } from "@/features/academic/certificates";

export const Route = createFileRoute("/academic/certificates")({ component: AcademicCertificates });
