import { useState } from "react";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { authApi, type ActivationCheck, type ActivationResult } from "@/api/auth";
import { ApiError, errorMessage } from "@/api/client";
import { useAuth } from "@/auth/auth";
import { AuthPage } from "@/components/lms/auth-page";
import { PasswordChecklist, passwordReady } from "@/components/lms/password-checklist";
import { PasswordField } from "@/components/lms/password-field";
import { QueryView, Section, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useT, type TranslationKey } from "@/lib/i18n";

export const Route = createFileRoute("/activate")({
  validateSearch: (search: Record<string, unknown>): { token?: string } =>
    typeof search["token"] === "string" && search["token"] ? { token: search["token"] } : {},
  component: Activate,
});

const PROBLEM: Record<Exclude<ActivationCheck["status"], "valid">, TranslationKey> = {
  expired: "linkExpired",
  used: "linkUsed",
  revoked: "linkReplaced",
};

/** The page behind the link a student or a new staff member gets: choose a password, get signed in, see what to do next. */
function Activate() {
  const { token } = Route.useSearch();
  const t = useT();
  const [result, setResult] = useState<ActivationResult | null>(null);
  const check = useQuery({ queryKey: ["activation", token], queryFn: () => authApi.checkActivation(token!), enabled: Boolean(token), retry: false });

  if (!token) {
    return (
      <AuthPage>
        <Section title={t("activateAccount")}>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{t("activateHelp")}</p>
            <Button asChild variant="outline" className="tap w-full">
              <Link to="/login">{t("goToSignIn")}</Link>
            </Button>
          </div>
        </Section>
      </AuthPage>
    );
  }
  if (result) return <AllSet result={result} />;

  return (
    <AuthPage>
      <Section title={t("activateAccount")}>
        {check.isError && check.error instanceof ApiError && check.error.status === 404 ? (
          <Problem message={t("linkNotFound")} />
        ) : (
          <QueryView query={check}>
            {(info) =>
              info.status === "valid" ? (
                <ActivationForm token={token} info={info} onDone={setResult} />
              ) : (
                <Problem message={t(PROBLEM[info.status])} signIn={info.status === "used"} />
              )
            }
          </QueryView>
        )}
      </Section>
    </AuthPage>
  );
}

function Problem({ message, signIn = true }: { message: string; signIn?: boolean }) {
  const t = useT();
  return (
    <div className="space-y-3">
      <StatusNote tone="danger">{message}</StatusNote>
      <p className="text-sm text-muted-foreground">{t("linkAskBranch")}</p>
      {signIn && (
        <Button asChild variant="outline" className="tap">
          <Link to="/login">{t("goToSignIn")}</Link>
        </Button>
      )}
    </div>
  );
}

function ActivationForm({ token, info, onDone }: { token: string; info: ActivationCheck; onDone: (result: ActivationResult) => void }) {
  const t = useT();
  const { startSession } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const activate = useMutation({
    mutationFn: () => authApi.activate(token, password),
    onSuccess: (result) => {
      startSession(result);
      onDone(result);
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
      <div>
        <p className="font-medium">{t("welcomeName", { name: info.full_name })}</p>
        <p className="text-sm text-muted-foreground">{info.student_code ?? info.email}</p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="activate-password">{t("chooseYourPassword")}</Label>
        <PasswordField id="activate-password" autoComplete="new-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="activate-confirm">{t("confirmPassword")}</Label>
        <PasswordField id="activate-confirm" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </div>
      <PasswordChecklist password={password} confirm={confirm} minLength={info.password_min_length} />
      {activate.isError && (
        <p role="alert" className="text-sm font-medium text-danger">
          ⚠ {errorMessage(activate.error)}
        </p>
      )}
      <Button type="submit" className="tap w-full" disabled={activate.isPending || !passwordReady(password, confirm, info.password_min_length)}>
        {activate.isPending && <Loader2 className="animate-spin" />}
        {t("activateNow")}
      </Button>
    </form>
  );
}

/** Success: the person is already signed in. A student sees their Student ID (they sign in with it next time). */
function AllSet({ result }: { result: ActivationResult }) {
  const t = useT();
  const navigate = useNavigate();
  return (
    <AuthPage>
      <Section title={t("allSet")}>
        <div className="space-y-4">
          <StatusNote tone="success">{t("welcomeName", { name: result.user.full_name })}</StatusNote>
          {result.student_code ? (
            <div className="rounded-lg border bg-muted/40 p-4">
              <p className="text-xs text-muted-foreground">{t("yourStudentId")}</p>
              <p className="font-mono text-lg font-semibold" data-testid="student-id">
                {result.student_code}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{t("studentIdHelp")}</p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{t("staffSignInHelp")}</p>
          )}
          <Button className="tap w-full" autoFocus onClick={() => void navigate({ to: result.home_route, replace: true })}>
            {t("goToHome")}
          </Button>
        </div>
      </Section>
    </AuthPage>
  );
}
