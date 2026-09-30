import { createFileRoute } from "@tanstack/react-router";
import { AskNipuna } from "@/features/student/ask-nipuna";

export const Route = createFileRoute("/ask-nipuna")({ component: AskNipuna });
