import { createFileRoute } from "@tanstack/react-router";
import { TrainerStudents } from "@/features/trainer/students";

export const Route = createFileRoute("/trainer/students")({ component: TrainerStudents });
