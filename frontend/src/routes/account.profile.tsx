import { createFileRoute } from "@tanstack/react-router";
import { Profile } from "@/features/student/profile";

/** Shared profile for every signed-in user; staff reach it from the account menu. */
export const Route = createFileRoute("/account/profile")({ component: Profile });
