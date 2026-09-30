import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { profileApi } from "@/api/profile";
import { ConfirmAction, KeyValue, Note, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDateTime, fmtDate } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { useLanguage, useT } from "@/lib/i18n";
import type { Language } from "@/api/types";

export function Profile() {
  const t = useT();
  const { lang, setLang } = useLanguage();
  const query = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  const refresh = { invalidate: [["profile"], ["me"]] };
  const setLanguage = useApiMutation((language: Language) => profileApi.setLanguage(language), refresh);
  const signOut = useApiMutation((sessionId: string) => profileApi.signOutDevice(sessionId), { ...refresh, success: "Signed out" });
  const signOutOthers = useApiMutation(() => profileApi.signOutOthers(), { ...refresh, success: (r) => `${r.signed_out} other session(s) signed out` });

  const choose = (language: Language) => {
    setLang(language);
    setLanguage.mutate(language);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <PageHead title={t("profile")} />
      <QueryView query={query}>
        {(profile) => {
          const student = profile.student;
          return (
            <>
              {student && (
                <Section title="Identity">
                  <KeyValue
                    items={[
                      ["Student Master ID", <span className="font-mono">{student.student_code}</span>],
                      ["Name", lang === "te" && student.name_te ? student.name_te : student.full_name],
                      ["Email", student.email ?? "No email on file (optional)"],
                      [
                        "Mobile",
                        <>
                          {student.mobile_masked ?? "—"} <span className="text-xs text-muted-foreground">({student.mobile_note})</span>
                        </>,
                      ],
                      ["Original / admitting branch", student.original_branch.branch_name],
                      ["Current service branch", student.service_branch.branch_name],
                      ["Activation", <StatusBadge>{student.activation_status}</StatusBadge>],
                    ]}
                  />
                </Section>
              )}
              {!student && (
                <Section title="Identity">
                  <KeyValue
                    items={[
                      ["Name", profile.user.full_name],
                      ["Email", profile.user.email ?? "—"],
                      ["Access", profile.scopes.map((s) => `${s.role_name}${s.branch_name ? ` — ${s.branch_name}` : ""}`).join(", ")],
                    ]}
                  />
                </Section>
              )}
              {student && (
                <Section title={t("language")}>
                  <div className="flex gap-2">
                    <Button variant={lang === "en" ? "default" : "outline"} onClick={() => choose("en")}>
                      English
                    </Button>
                    <Button variant={lang === "te" ? "default" : "outline"} onClick={() => choose("te")}>
                      <span lang="te">తెలుగు</span>
                    </Button>
                  </div>
                </Section>
              )}
              <Section
                title="Devices & sessions"
                actions={
                  profile.devices.length > 1 && (
                    <ConfirmAction
                      title="Sign out other devices?"
                      description="Every session except this one is ended."
                      confirmLabel="Sign out others"
                      onConfirm={async () => void (await signOutOthers.mutateAsync())}
                    >
                      <Button variant="outline" size="sm">
                        Sign out other devices
                      </Button>
                    </ConfirmAction>
                  )
                }
              >
                <ul className="space-y-2 text-sm">
                  {profile.devices.map((d) => (
                    <li key={d.session_id} className="flex flex-wrap items-center justify-between gap-2">
                      <span>
                        {d.label} — {d.current ? "this device" : fmtDateTime(d.last_seen_at)}
                      </span>
                      {d.current ? (
                        <StatusBadge tone="success">Active</StatusBadge>
                      ) : (
                        <Button variant="outline" size="sm" onClick={() => signOut.mutate(d.session_id)} aria-label={`Sign out ${d.label}`}>
                          Sign out
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </Section>
              <Section title="Password & recovery">
                <KeyValue
                  items={[
                    [
                      "Password",
                      profile.password_changed_at ? `Set by you · last changed ${fmtDate(profile.password_changed_at)}` : "Set by you at activation",
                    ],
                    [
                      "Recovery",
                      student
                        ? (student.recovery.email_on_file ? "Email on file. " : "No email on file. ") + student.recovery.method
                        : "A Super Admin resets a staff password.",
                    ],
                    ["MFA", student ? student.mfa_status : "Not Configured"],
                    ["Last sign-in", fmtDateTime(profile.last_login_at)],
                  ]}
                />
                <div className="mt-3">
                  <Button variant="outline" asChild>
                    <Link to="/change-password">Change password</Link>
                  </Button>
                </div>
                <div className="mt-3">
                  <Note>Staff cannot view or set your password.</Note>
                </div>
              </Section>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
