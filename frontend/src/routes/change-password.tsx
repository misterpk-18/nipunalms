import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { authApi } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth";
import { AuthPage } from "@/components/lms/auth-page";
import { PasswordField } from "@/components/lms/password-field";
import { Section } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/change-password")({ component: ChangePassword });

function ChangePassword() {
  const { refresh, profile, signOut } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mismatch = confirm.length > 0 && next !== confirm;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await authApi.changePassword(current, next);
      await refresh();
      void navigate({ to: "/" });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthPage>
      <Section title="Set a new password">
        <p className="mb-4 text-sm text-muted-foreground">
          {profile?.user.must_change_password ? "Your account has a temporary password. Choose a new one to continue." : "Change your password."}
        </p>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="current-password">Current password</Label>
            <PasswordField id="current-password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-password">New password</Label>
            <PasswordField id="new-password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
            <p className="text-xs text-muted-foreground">At least 10 characters. Your other sessions will be signed out.</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm-password">Confirm new password</Label>
            <PasswordField id="confirm-password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            {mismatch && <p className="text-xs text-danger">Passwords don't match</p>}
          </div>
          {error && (
            <p role="alert" className="rounded-md bg-destructive/10 p-2.5 text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" className="tap" disabled={busy || !current || !next || next !== confirm}>
            Change password
          </Button>
        </form>
        <button className="mt-4 text-xs text-muted-foreground underline" onClick={() => void signOut().then(() => navigate({ to: "/login" }))}>
          Sign out instead
        </button>
      </Section>
    </AuthPage>
  );
}
