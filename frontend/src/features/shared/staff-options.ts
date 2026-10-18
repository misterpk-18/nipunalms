/** Every active staff member as `{value, label}` for a "who" select (the owner of a setup item, the assignee of an issue). */
import { useQuery } from "@tanstack/react-query";
import { adminApi, adminKeys } from "@/api/admin";

export function useAllStaff() {
  const query = useQuery({ queryKey: adminKeys.staffOptions, queryFn: adminApi.staffOptions, staleTime: 5 * 60_000 });
  const options = (query.data ?? []).map((u) => ({ value: u.user_id, label: u.roles.length ? `${u.full_name} (${u.roles.join(", ")})` : u.full_name }));
  return { ...query, options };
}
