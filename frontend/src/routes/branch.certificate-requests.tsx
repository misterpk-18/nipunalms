import { createFileRoute } from "@tanstack/react-router";
import { BranchCertificateRequests } from "@/features/branch/certificate-requests";

export const Route = createFileRoute("/branch/certificate-requests")({ component: BranchCertificateRequests });
