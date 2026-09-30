/**
 * Session state: the current profile (/auth/me), sign in / sign out, and the fresh-auth password prompt used by
 * sensitive actions.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi, type Profile } from "@/api/auth";
import { errorMessage, getToken, registerAuthHandlers, setToken } from "@/api/client";
import type { RoleCode, Workspace } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type AuthContextValue = {
  status: "anonymous" | "loading" | "authenticated";
  profile: Profile | null;
  roles: RoleCode[];
  /** Workspaces this user may open (from the API; a Super Admin also holds academic and branch). */
  workspaces: Workspace[];
  hasRole: (...roles: RoleCode[]) => boolean;
  signIn: (login: string, password: string) => Promise<Profile>;
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

  const profile = hasToken ? (me.data ?? null) : null;
  const roles = useMemo(() => [...new Set(profile?.scopes.map((s) => s.role_code) ?? [])], [profile]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status: !hasToken ? "anonymous" : profile ? "authenticated" : "loading",
      profile,
      roles,
      workspaces: profile?.workspaces ?? [],
      hasRole: (...wanted) => wanted.some((r) => roles.includes(r)),
      signIn: async (login, password) => {
        const result = await authApi.login(login, password);
        setToken(result.token);
        const { token: _token, expires_at: _expires, ...rest } = result;
        queryClient.setQueryData(["me"], rest);
        setHasToken(true);
        return rest;
      },
      signOut: async () => {
        try {
          await authApi.logout();
        } finally {
          clearSession();
        }
      },
      refresh: () => me.refetch(),
    }),
    [clearSession, hasToken, me, profile, queryClient, roles],
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
