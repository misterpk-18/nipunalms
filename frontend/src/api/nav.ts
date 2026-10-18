import { useQuery } from "@tanstack/react-query";
import { get } from "./client";
import type { Workspace } from "./types";

/** `{badgeKey: n}` for one workspace: how many items wait for the person on each navigation item. */
export type NavCounts = Record<string, number>;

export type GettingStartedStep = { key: string; label: string; done: boolean; to: string };
export type GettingStarted = { workspace: Workspace; steps: GettingStartedStep[]; complete: boolean };

export type SearchRecord = { kind: "student" | "batch" | "certificate"; id: number; title: string; subtitle: string };

export const navApi = {
  /** The role comes from the session; a Branch Manager's branch too. */
  counts: () => get<NavCounts>("/me/nav-counts"),
  gettingStarted: () => get<GettingStarted>("/me/getting-started"),
  search: (q: string) => get<SearchRecord[]>("/search", { q }),
};

/** Count badges for the navigation; polled with the notification bell. */
export function useNavCounts() {
  return useQuery({
    queryKey: ["nav", "counts"],
    queryFn: navApi.counts,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useGettingStarted() {
  return useQuery({ queryKey: ["nav", "getting-started"], queryFn: navApi.gettingStarted, staleTime: 60_000 });
}

/** Records matching the text, within what the user may open. Waits for two characters. */
export function useRecordSearch(text: string) {
  const q = text.trim();
  return useQuery({
    queryKey: ["nav", "search", q],
    queryFn: () => navApi.search(q),
    enabled: q.length >= 2,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}
