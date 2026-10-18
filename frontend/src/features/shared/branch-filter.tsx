/** "All branches" or one branch: the filter Super Admin and Founder screens use for cross-branch views (a Branch Manager has one fixed branch and no filter). */
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/api/admin";
import { NativeSelect } from "@/components/lms/forms";

export function useBranchOptions() {
  return useQuery({ queryKey: ["reference", "branches"], queryFn: adminApi.branches, staleTime: 5 * 60_000 });
}

export function BranchFilter({ value, onChange }: { value: number | null; onChange: (branchId: number | null) => void }) {
  const branches = useBranchOptions();
  return (
    <NativeSelect
      aria-label="Branch"
      placeholder="All branches"
      value={value === null ? "" : String(value)}
      options={(branches.data ?? []).map((b) => ({ value: b.branch_id, label: b.branch_name }))}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
    />
  );
}
