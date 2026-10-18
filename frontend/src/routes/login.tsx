import { useState } from "react";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { ApiError, errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth";
import { AuthPage } from "@/components/lms/auth-page";
import { PasswordField } from "@/components/lms/password-field";
import { Section } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useT } from "@/lib/i18n";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>): { redirect?: string } =>
    typeof search["redirect"] === "string" && search["redirect"].startsWith("/") ? { redirect: search["redirect"] } : {},
  component: Login,
});

/** One form for everyone: a student signs in with the Student ID, staff with their email. */
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
      // A Branch Manager with several branches picks one next (the root renders the branch step)
      if (profile.needs_branch) return;
      void navigate({ to: profile.user.must_change_password ? "/change-password" : (redirect ?? profile.home_route), replace: true });
    } catch (e) {
      setError(e instanceof ApiError && e.code === "VALIDATION_ERROR" ? t("requiredField") : errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthPage>
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
            <p className="text-xs text-muted-foreground">{t("loginHelp")}</p>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="login-password">{t("password")}</Label>
              <Link to="/forgot-password" className="text-sm text-primary underline-offset-4 hover:underline">
                {t("forgot")}
              </Link>
            </div>
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
        <p className="mt-5 border-t pt-4 text-center text-sm text-muted-foreground">
          {t("firstTime")}{" "}
          <Link to="/activate" className="font-medium text-primary underline-offset-4 hover:underline">
            {t("activateLink")}
          </Link>
        </p>
      </Section>
    </AuthPage>
  );
}
