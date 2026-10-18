import { createFileRoute } from "@tanstack/react-router";
import { BranchQuestions } from "@/features/branch/questions";

export const Route = createFileRoute("/branch/questions")({ component: BranchQuestions });
