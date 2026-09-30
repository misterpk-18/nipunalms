import { createFileRoute } from "@tanstack/react-router";
import { Profile } from "@/features/student/profile";

export const Route = createFileRoute("/profile")({ component: Profile });
