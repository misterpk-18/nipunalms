import { createFileRoute } from "@tanstack/react-router";
import { TrainerAskNipuna } from "@/features/trainer/ask-nipuna";

export const Route = createFileRoute("/trainer/ask-nipuna")({ component: TrainerAskNipuna });
