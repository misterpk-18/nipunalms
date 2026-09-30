import { useState } from "react";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { authApi } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { AuthPage } from "@/components/lms/auth-page";
import { PasswordField } from "@/components/lms/password-field";
import { QueryView, Section, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useT } from "@/lib/i18n";

export const Route = createFileRoute("/activate")({
  validateSearch: (search: Record<string, unknown>): { token?: string } =>
    typeof search["token"] === "string" && search["token"] ? { token: search["token"] } : {},
  component: Activate,
});

function Activate() {
  const { token } = Route.useSearch();
  const t = useT();
  const check = useQuery({ queryKey: ["activation", token], queryFn: () => authApi.checkActivation(token!), enabled: Boolean(token), retry: false });

  return (
    <AuthPage>
      <Section title={t("activateAccount")}>
        {!token ? (
          <StatusNote state="Error">{t("forgotHelp")}</StatusNote>
        ) : (
          <QueryView query={check}>
            {(result) =>
              result.status === "valid" ? (
                <ActivationForm token={token} studentCode={result.student_code_masked} />
              ) : (
                <div className="space-y-3">
                  <StatusNote state="Error">
                    {result.status === "expired" ? "This activation link has expired." : "This activation link has already been used."}
                  </StatusNote>
                  {result.status === "expired" && <p className="text-sm text-muted-foreground">{t("forgotHelp")}</p>}
                  <Button asChild variant="outline" className="tap">
                    <Link to="/login">{t("goToSignIn")}</Link>
                  </Button>
                </div>
              )
            }
          </QueryView>
        )}
      </Section>
    </AuthPage>
  );
}

function ActivationForm({ token, studentCode }: { token: string; studentCode: string }) {
  const t = useT();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const mismatch = confirm.length > 0 && password !== confirm;
  const activate = useMutation({
    mutationFn: () => authApi.activate(token, password),
    onSuccess: () => {
      toast.success(t("activated"));
      void navigate({ to: "/login", replace: true });
    },
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        activate.mutate();
      }}
    >
      <p className="text-sm text-muted-foreground">{studentCode}</p>
      <div className="space-y-1.5">
        <Label htmlFor="activate-password">{t("newPassword")}</Label>
        <PasswordField id="activate-password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <p className="text-xs text-muted-foreground">At least 10 characters.</p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="activate-confirm">{t("confirmPassword")}</Label>
        <PasswordField id="activate-confirm" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        {mismatch && <p className="text-xs text-danger">{t("passwordMismatch")}</p>}
      </div>
      {activate.isError && (
        <p role="alert" className="rounded-md bg-destructive/10 p-2.5 text-sm text-destructive">
          {errorMessage(activate.error)}
        </p>
      )}
      <Button type="submit" className="tap w-full" disabled={activate.isPending || !password || password !== confirm}>
        {t("activateNow")}
      </Button>
    </form>
  );
}
