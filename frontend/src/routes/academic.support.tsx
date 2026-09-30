import { createFileRoute } from "@tanstack/react-router";
import { AcademicSupport } from "@/features/academic/support";

export const Route = createFileRoute("/academic/support")({ component: AcademicSupport });
