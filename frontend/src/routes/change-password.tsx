import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { authApi } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth";
import { AuthPage } from "@/components/lms/auth-page";
import { PasswordChecklist, passwordReady } from "@/components/lms/password-checklist";
import { PasswordField } from "@/components/lms/password-field";
import { Section } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useT } from "@/lib/i18n";

export const Route = createFileRoute("/change-password")({ component: ChangePassword });

const MIN_LENGTH = 10;

function ChangePassword() {
  const { refresh, profile, signOut } = useAuth();
  const navigate = useNavigate();
  const t = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await authApi.changePassword(current, next);
      await refresh();
      toast.success(t("passwordChanged"));
      void navigate({ to: "/" });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthPage>
      <Section title={t("changePasswordTitle")}>
        <p className="mb-4 text-sm text-muted-foreground">{profile?.user.must_change_password ? t("changePasswordTemp") : t("changePasswordIntro")}</p>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="current-password">{t("currentPassword")}</Label>
            <PasswordField id="current-password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-password">{t("newPassword")}</Label>
            <PasswordField id="new-password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm-password">{t("confirmPassword")}</Label>
            <PasswordField id="confirm-password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          <PasswordChecklist password={next} confirm={confirm} minLength={MIN_LENGTH} differsFrom={current} />
          {error && (
            <p role="alert" className="rounded-md bg-destructive/10 p-2.5 text-sm text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" className="tap" disabled={busy || !current || !passwordReady(next, confirm, MIN_LENGTH, current)}>
            {t("changePassword")}
          </Button>
        </form>
        <button className="mt-4 text-xs text-muted-foreground underline" onClick={() => void signOut().then(() => navigate({ to: "/login" }))}>
          {t("signOutInstead")}
        </button>
      </Section>
    </AuthPage>
  );
}
