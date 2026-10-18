/**
 * Session state: the current profile (/auth/me), sign in / sign out, and the fresh-auth password prompt used by
 * sensitive actions.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi, type LoginResult, type Profile } from "@/api/auth";
import { errorMessage, getToken, registerAuthHandlers, setToken } from "@/api/client";
import type { BranchRef, RoleCode, Workspace } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type AuthContextValue = {
  status: "anonymous" | "loading" | "authenticated";
  profile: Profile | null;
  /** The session's one role, as a list (empty while signed out). */
  roles: RoleCode[];
  /** The one workspace of the session's role (role separation: one role per account). */
  workspace: Workspace;
  /** Always just `[workspace]`; kept for the route guard (`canOpen`). */
  workspaces: Workspace[];
  /** The Branch Manager's branch for this session; null for every other role (and while a branch pick is pending). */
  branchId: number | null;
  /** The branches the account may work in (a Branch Manager's choices at sign-in; the "Change branch" menu item needs more than one). */
  allowedBranches: BranchRef[];
  /** For the two curriculum files that R6 deletes. Nothing else reads the role: routes pass each screen its config. */
  hasRole: (...roles: RoleCode[]) => boolean;
  signIn: (login: string, password: string) => Promise<Profile>;
  /** Branch Manager with several branches: fix the branch for this session after sign-in. */
  selectBranch: (branchId: number) => Promise<Profile>;
  /** Ends the session so the Branch Manager signs in again and picks another branch. */
  changeBranch: () => Promise<void>;
  /** Start a session from a login-shaped response (activation signs the person in). */
  startSession: (result: LoginResult) => Profile;
  signOut: () => Promise<void>;
  refresh: () => Promise<unknown>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, onSignedOut }: { children: ReactNode; onSignedOut: () => void }) {
  const queryClient = useQueryClient();
  const [hasToken, setHasToken] = useState(() => Boolean(getToken()));
  const [freshAuth, setFreshAuth] = useState<{ resolve: (ok: boolean) => void } | null>(null);
  const signedOut = useRef(onSignedOut);
  signedOut.current = onSignedOut;

  const me = useQuery({ queryKey: ["me"], queryFn: authApi.me, enabled: hasToken, staleTime: 5 * 60_000, retry: false });

  const clearSession = useCallback(() => {
    setToken(null);
    setHasToken(false);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    registerAuthHandlers({
      unauthenticated: () => {
        clearSession();
        signedOut.current();
      },
      freshAuthRequired: () => new Promise<boolean>((resolve) => setFreshAuth({ resolve })),
      passwordChangeRequired: () => void queryClient.invalidateQueries({ queryKey: ["me"] }),
    });
  }, [clearSession, queryClient]);

  const startSession = useCallback(
    (result: LoginResult): Profile => {
      setToken(result.token);
      const { token: _token, expires_at: _expires, ...rest } = result;
      const profile: Profile = {
        user: rest.user,
        role: rest.role,
        workspace: rest.workspace,
        branch: rest.branch,
        needs_branch: rest.needs_branch,
        branches: rest.branches,
        scopes: rest.scopes,
        allowed_branches: rest.allowed_branches,
        workspaces: rest.workspaces,
        home_route: rest.home_route,
        student: rest.student,
      };
      queryClient.setQueryData(["me"], profile);
      setHasToken(true);
      return profile;
    },
    [queryClient],
  );

  const profile = hasToken ? (me.data ?? null) : null;
  const roles = useMemo<RoleCode[]>(() => (profile?.role ? [profile.role.role_code] : []), [profile]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status: !hasToken ? "anonymous" : profile ? "authenticated" : "loading",
      profile,
      roles,
      workspace: profile?.workspace ?? "student",
      workspaces: profile?.workspace ? [profile.workspace] : [],
      branchId: profile?.branch?.branch_id ?? null,
      allowedBranches: profile?.branches?.length ? profile.branches : (profile?.allowed_branches ?? []),
      hasRole: (...wanted) => wanted.some((r) => roles.includes(r)),
      signIn: async (login, password) => startSession(await authApi.login(login, password)),
      selectBranch: async (branchId) => {
        const picked = await authApi.selectBranch(branchId);
        queryClient.clear();
        queryClient.setQueryData(["me"], picked);
        return picked;
      },
      changeBranch: async () => {
        try {
          await authApi.changeBranch();
        } finally {
          clearSession();
        }
      },
      startSession,
      signOut: async () => {
        try {
          await authApi.logout();
        } finally {
          clearSession();
        }
      },
      refresh: () => me.refetch(),
    }),
    [clearSession, hasToken, me, profile, queryClient, roles, startSession],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
      <FreshAuthDialog
        open={Boolean(freshAuth)}
        onDone={(ok) => {
          freshAuth?.resolve(ok);
          setFreshAuth(null);
        }}
      />
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}

function FreshAuthDialog({ open, onDone }: { open: boolean; onDone: (ok: boolean) => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setPassword("");
      setError(null);
    }
  }, [open]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await authApi.reauthenticate(password);
      onDone(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onDone(false)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm your password</DialogTitle>
          <DialogDescription>This action needs a recent sign-in. Enter your password to continue.</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
          className="space-y-2"
        >
          <Label htmlFor="fresh-auth-password">Password</Label>
          <Input id="fresh-auth-password" type="password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={() => onDone(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!password || busy}>
              Continue
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
