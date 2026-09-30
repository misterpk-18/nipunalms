import { createFileRoute } from "@tanstack/react-router";
import { ModuleDetail } from "@/features/student/module-detail";

export const Route = createFileRoute("/modules/$moduleId")({ component: ModuleDetail });
