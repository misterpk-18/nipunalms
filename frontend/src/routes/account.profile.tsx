import { createFileRoute } from "@tanstack/react-router";
import { useAuth } from "@/auth/auth";
import { WORKSPACE_LABELS } from "@/auth/access";
import { StaffProfile } from "@/features/shared/staff-profile";

/** A staff member's account page; they reach it from the account menu. Role and branch come from the session (one role per account). */
function ProfileRoute() {
  const { profile, workspace } = useAuth();
  const allBranches = workspace === "admin" || workspace === "founder";
  return (
    <StaffProfile
      role={profile?.role?.role_name ?? WORKSPACE_LABELS[workspace]}
      branchLabel={profile?.branch?.branch_name ?? (allBranches ? "All branches" : "—")}
    />
  );
}

export const Route = createFileRoute("/account/profile")({ component: ProfileRoute });
