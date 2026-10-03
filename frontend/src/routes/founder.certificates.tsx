import { createFileRoute } from "@tanstack/react-router";
import { FounderCertificates } from "@/features/founder/certificates";

export const Route = createFileRoute("/founder/certificates")({ component: FounderCertificates });
