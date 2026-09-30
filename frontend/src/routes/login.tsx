import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { ApiError, errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth";
import { AuthPage } from "@/components/lms/auth-page";
import { PasswordField } from "@/components/lms/password-field";
import { Note, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useT, type TranslationKey } from "@/lib/i18n";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>): { redirect?: string } =>
    typeof search["redirect"] === "string" && search["redirect"].startsWith("/") ? { redirect: search["redirect"] } : {},
  component: Login,
});

const ACCESS_STATES: TranslationKey[] = ["accountCreated", "activationPending", "activated", "courseAccessReleased"];

function Login() {
  const { signIn } = useAuth();
  const { redirect } = Route.useSearch();
  const navigate = useNavigate();
  const t = useT();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!login.trim() || !password) {
      setError(t("requiredField"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const profile = await signIn(login.trim(), password);
      void navigate({ to: profile.user.must_change_password ? "/change-password" : (redirect ?? profile.home_route), replace: true });
    } catch (e) {
      setError(e instanceof ApiError && e.code === "VALIDATION_ERROR" ? t("requiredField") : errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthPage wide>
      <Section title={t("login")}>
        <form
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="login-id">{t("loginId")}</Label>
            <Input
              id="login-id"
              className="tap"
              autoComplete="username"
              autoFocus
              placeholder="NIT-STU-2026-004182"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              aria-invalid={Boolean(error) && !login}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="login-password">{t("password")}</Label>
            <PasswordField
              id="login-password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={Boolean(error) && !password}
            />
          </div>
          {error && (
            <p role="alert" className="text-sm font-medium text-danger">
              ⚠ {error}
            </p>
          )}
          <Button type="submit" className="tap w-full" disabled={busy}>
            {busy && <Loader2 className="animate-spin" />}
            {t("login")}
          </Button>
        </form>
        <div className="mt-4 space-y-3">
          <Note>
            <strong>{t("forgot")}</strong> {t("forgotHelp")}
          </Note>
          <Note>{t("passwordPrivate")}</Note>
        </div>
      </Section>
      <div className="space-y-4">
        <Section title={t("activationStatus")}>
          <ol className="space-y-3">
            {ACCESS_STATES.map((key, i) => (
              <li key={key} className="flex items-center gap-3">
                <span className="grid size-7 place-items-center rounded-full bg-muted text-xs font-bold text-muted-foreground">{i + 1}</span>
                <span className="flex-1">{t(key)}</span>
              </li>
            ))}
          </ol>
          <div className="mt-3">
            <StatusBadge tone="info">{t("accessAfterAllocation")}</StatusBadge>
          </div>
        </Section>
        <Section>
          <p className="text-xs text-muted-foreground">{t("oneLogin")}</p>
        </Section>
      </div>
    </AuthPage>
  );
}
