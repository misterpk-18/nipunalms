/** Page state kept in the address (`?tab=`, `?risk=`, `?request=`), so a link or a refresh opens the same view. */
import { useNavigate, useSearch } from "@tanstack/react-router";

type Params = Record<string, string | number | undefined>;

/** The current search values as text, and a setter that changes some of them (an empty or undefined value removes the key). */
export function useUrlParams(): [Record<string, string | undefined>, (patch: Params) => void] {
  const raw = useSearch({ strict: false }) as Record<string, unknown>;
  const navigate = useNavigate();
  const values: Record<string, string | undefined> = {};
  for (const [key, value] of Object.entries(raw)) if (value !== undefined && value !== null && value !== "") values[key] = String(value);
  const set = (patch: Params) => {
    const next: Record<string, unknown> = { ...raw, ...patch };
    for (const key of Object.keys(next)) if (next[key] === undefined || next[key] === "") delete next[key];
    void navigate({ to: ".", search: next as never, replace: true });
  };
  return [values, set];
}

/** The tab named in the address when it is one of `tabs`, else the first. */
export function pickTab<T extends string>(tabs: readonly T[], value: string | undefined): T {
  return tabs.find((t) => t === value) ?? tabs[0]!;
}
