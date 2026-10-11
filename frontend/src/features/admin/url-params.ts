/** Screen state kept in the address (a tab, a filter, a page, an open record) so a refresh or a link shows the same thing. */
import { useNavigate, useSearch } from "@tanstack/react-router";

export type Params = Record<string, string | undefined>;

/** The string search parameters of the current screen and a setter that merges a patch (an empty value removes the key). */
export function useUrlParams(): [Params, (patch: Params, options?: { replace?: boolean }) => void] {
  const raw = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  const params: Params = {};
  for (const [key, value] of Object.entries(raw))
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") params[key] = String(value);
  const set = (patch: Params, options: { replace?: boolean } = {}) => {
    const merged: Record<string, unknown> = { ...raw, ...patch };
    for (const key of Object.keys(merged)) if (merged[key] === undefined || merged[key] === "") delete merged[key];
    void navigate({ to: ".", search: (() => merged) as never, replace: options.replace ?? true });
  };
  return [params, set];
}

/** `?page=` as a number, 1 when absent. */
export const pageOf = (params: Params) => Math.max(1, Number(params["page"]) || 1);
