import { createFileRoute } from "@tanstack/react-router";
import { BranchPayments } from "@/features/branch/payments";

export const Route = createFileRoute("/branch/payments")({ component: BranchPayments });
