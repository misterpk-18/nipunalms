/** Staff of a branch by role, merged into one option list for a "who" field (cover, owner, host). */
import { useQueries } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";

export function useStaffOptions(branchId: number | undefined, roles: string[]) {
  const results = useQueries({
    queries: roles.map((role) => ({
      queryKey: ["delivery", "staff", role, branchId],
      queryFn: () => deliveryApi.staff(role, branchId!),
      enabled: !!branchId,
    })),
  });
  const seen = new Map<number, string>();
  for (const r of results) for (const u of r.data ?? []) seen.set(u.user_id, u.full_name);
  return [...seen].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label));
}
