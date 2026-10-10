import { useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { authApi } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { AuthPage } from "@/components/lms/auth-page";
import { PasswordChecklist, passwordReady } from "@/components/lms/password-checklist";
import { PasswordField } from "@/components/lms/password-field";
import { Section, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useT } from "@/lib/i18n";

export const Route = createFileRoute("/forgot-password")({ component: ForgotPassword });

const MIN_LENGTH = 10;

/** Self-service reset: ask for a code (sent by WhatsApp), then set a new password with it. */
function ForgotPassword() {
  const t = useT();
  const [login, setLogin] = useState("");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);

  const ask = useMutation({
    mutationFn: () => authApi.requestResetCode(login.trim()),
    onSuccess: () => setSent(true),
  });
  const save = useMutation({
    mutationFn: () => authApi.resetPassword(login.trim(), code.trim(), password),
    onSuccess: () => {
      toast.success(t("resetDone"));
      setDone(true);
    },
  });

  if (done) {
    return (
      <AuthPage>
        <Section title={t("resetTitle")}>
          <div className="space-y-4">
            <StatusNote tone="success">{t("resetDone")}</StatusNote>
            <Button asChild className="tap w-full">
              <Link to="/login">{t("login")}</Link>
            </Button>
          </div>
        </Section>
      </AuthPage>
    );
  }

  return (
    <AuthPage>
      <Section title={t("resetTitle")}>
        <div className="space-y-5">
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              ask.mutate();
            }}
          >
            <p className="text-sm text-muted-foreground">{t("resetAskHelp")}</p>
            <div className="space-y-1.5">
              <Label htmlFor="reset-login">{t("loginId")}</Label>
              <Input id="reset-login" className="tap" autoComplete="username" autoFocus value={login} onChange={(e) => setLogin(e.target.value)} />
            </div>
            {ask.isError && (
              <p role="alert" className="text-sm font-medium text-danger">
                ⚠ {errorMessage(ask.error)}
              </p>
            )}
            <Button type="submit" variant={sent ? "outline" : "default"} className="tap w-full" disabled={ask.isPending || !login.trim()}>
              {ask.isPending && <Loader2 className="animate-spin" />}
              {sent ? t("sendAgain") : t("sendCode")}
            </Button>
          </form>

          {sent && (
            <form
              className="space-y-4 border-t pt-4"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate();
              }}
            >
              <StatusNote tone="info">{t("codeSent")}</StatusNote>
              <p className="text-sm text-muted-foreground">{t("codeHelp")}</p>
              <div className="space-y-1.5">
                <Label htmlFor="reset-code">{t("codeLabel")}</Label>
                <Input
                  id="reset-code"
                  className="tap font-mono tracking-widest"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reset-password">{t("newPassword")}</Label>
                <PasswordField id="reset-password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reset-confirm">{t("confirmPassword")}</Label>
                <PasswordField id="reset-confirm" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
              </div>
              <PasswordChecklist password={password} confirm={confirm} minLength={MIN_LENGTH} />
              {save.isError && (
                <p role="alert" className="text-sm font-medium text-danger">
                  ⚠ {errorMessage(save.error)}
                </p>
              )}
              <Button type="submit" className="tap w-full" disabled={save.isPending || code.length !== 6 || !passwordReady(password, confirm, MIN_LENGTH)}>
                {save.isPending && <Loader2 className="animate-spin" />}
                {t("setNewPassword")}
              </Button>
            </form>
          )}
          <Button asChild variant="ghost" className="tap w-full">
            <Link to="/login">{t("backToSignIn")}</Link>
          </Button>
        </div>
      </Section>
    </AuthPage>
  );
}
