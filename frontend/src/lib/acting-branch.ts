/**
 * The branch a multi-branch user is looking at (the branch picker in the header's "Acting as" switcher). It is a per-person
 * convenience kept in this browser, keyed by user; null means every branch the person may see.
 */
import { useCallback, useSyncExternalStore } from "react";

const key = (userId: number) => `nipunalms.actingBranch.${userId}`;
const listeners = new Set<() => void>();

function read(userId: number): number | null {
  try {
    const raw = window.localStorage.getItem(key(userId));
    return raw ? Number(raw) : null;
  } catch {
    return null;
  }
}

function write(userId: number, branchId: number | null) {
  try {
    if (branchId === null) window.localStorage.removeItem(key(userId));
    else window.localStorage.setItem(key(userId), String(branchId));
  } catch {
    // storage blocked: the choice then lasts only until the next reload
  }
  listeners.forEach((notify) => notify());
}

const subscribe = (notify: () => void) => {
  listeners.add(notify);
  return () => void listeners.delete(notify);
};

/** The chosen branch, only while it is still one of `allowed`; otherwise null (all branches). */
export function usePickedBranch(userId: number | undefined, allowed: number[]): [number | null, (branchId: number | null) => void] {
  const stored = useSyncExternalStore(
    subscribe,
    () => (userId === undefined ? null : read(userId)),
    () => null,
  );
  const set = useCallback((branchId: number | null) => userId !== undefined && write(userId, branchId), [userId]);
  return [stored !== null && allowed.includes(stored) ? stored : null, set];
}
