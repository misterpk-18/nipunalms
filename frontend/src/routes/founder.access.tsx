import { createFileRoute } from "@tanstack/react-router";
import { FounderAccess } from "@/features/founder/access";

export const Route = createFileRoute("/founder/access")({ component: FounderAccess });
