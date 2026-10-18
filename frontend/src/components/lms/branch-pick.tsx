import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth";
import { AuthPage } from "@/components/lms/auth-page";
import { Section } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";

/**
 * The second step of sign-in for a Branch Manager with several branches: the account is signed in but nothing else works until
 * one branch is fixed for the session. Picking one lands on the account's home route; "Change branch" in the account menu returns here.
 */
export function BranchPick({ redirect }: { redirect?: string | undefined }) {
  const { profile, allowedBranches, selectBranch, signOut } = useAuth();
  const navigate = useNavigate();
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pick = async (branchId: number) => {
    setBusyId(branchId);
    setError(null);
    try {
      const next = await selectBranch(branchId);
      void navigate({ to: next.user.must_change_password ? "/change-password" : (redirect ?? next.home_route), replace: true });
    } catch (e) {
      setError(errorMessage(e));
      setBusyId(null);
    }
  };

  return (
    <AuthPage>
      <Section title="Choose a branch">
        <p className="mb-4 text-sm text-muted-foreground">
          {profile?.user.full_name ? `${profile.user.full_name}, you` : "You"} manage more than one branch. Pick the one to work in for this session.
        </p>
        <ul className="space-y-2">
          {allowedBranches.map((b) => (
            <li key={b.branch_id}>
              <Button variant="outline" className="tap w-full justify-start" disabled={busyId !== null} onClick={() => void pick(b.branch_id)}>
                {busyId === b.branch_id && <Loader2 className="animate-spin" />}
                {b.branch_name}
              </Button>
            </li>
          ))}
        </ul>
        {error && (
          <p role="alert" className="mt-3 text-sm font-medium text-danger">
            ⚠ {error}
          </p>
        )}
        <p className="mt-5 border-t pt-4 text-center text-sm">
          <button className="text-primary underline-offset-4 hover:underline" onClick={() => void signOut().then(() => navigate({ to: "/login" }))}>
            Sign in as someone else
          </button>
        </p>
      </Section>
    </AuthPage>
  );
}
