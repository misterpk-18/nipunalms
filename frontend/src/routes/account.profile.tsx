import { createFileRoute } from "@tanstack/react-router";
import { StaffProfile } from "@/features/shared/staff-profile";

/** A staff member's account page; they reach it from the account menu. */
export const Route = createFileRoute("/account/profile")({ component: StaffProfile });
