import { createFileRoute } from "@tanstack/react-router";
import { TrainerStudentPage } from "@/features/trainer/student-page";

/** One student inside the trainer's batches: attendance, work, results, support flags and "Flag this student". */
export const Route = createFileRoute("/trainer/students/$id")({ component: TrainerStudentPage });
