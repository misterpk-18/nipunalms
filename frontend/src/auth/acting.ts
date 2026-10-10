/** What the signed-in person is currently acting as: the workspace's branch pick (only the Branch Manager workspace is branch-scoped). */
import type { Workspace } from "@/api/types";
import { useAuth } from "@/auth/auth";
import { usePickedBranch } from "@/lib/acting-branch";

export function useActing(workspace: Workspace) {
  const { profile } = useAuth();
  const branches = profile?.allowed_branches ?? [];
  const [picked, setPicked] = usePickedBranch(
    profile?.user.user_id,
    branches.map((b) => b.branch_id),
  );
  const canPick = workspace === "branch" && branches.length > 1;
  return { branches, canPick, branchId: canPick ? picked : null, setBranchId: setPicked };
}
