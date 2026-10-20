import { createFileRoute } from "@tanstack/react-router";
import { BranchQuestions } from "@/features/branch/questions";

export const Route = createFileRoute("/admin/questions")({ component: () => <BranchQuestions /> });
