/** A staff member's account page (the student's is My Account, `features/student/account.tsx`): who you are, messages, devices, password. */
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { profileApi } from "@/api/profile";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { KeyValue, Note, PageHead, QueryView, Section, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDateTime, fmtDate } from "@/features/shared/format";
import { NotificationPreferences } from "@/features/shared/notification-preferences";
import { useApiMutation } from "@/lib/mutation";

export function StaffProfile() {
  const query = useQuery({ queryKey: ["profile"], queryFn: profileApi.get });
  const refresh = { invalidate: [["profile"], ["me"]] };
  const signOut = useApiMutation((sessionId: string) => profileApi.signOutDevice(sessionId), { ...refresh, success: "Signed out" });
  const signOutOthers = useApiMutation(() => profileApi.signOutOthers(), { ...refresh, success: (r) => `${r.signed_out} other session(s) signed out` });

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <PageHead title="Profile" />
      <QueryView query={query}>
        {(profile) => (
          <>
            <Section title="Identity">
              <KeyValue
                items={[
                  ["Name", profile.user.full_name],
                  ["Email", profile.user.email ?? "—"],
                  ["Role", [...new Set(profile.scopes.map((s) => s.role_name))].join(", ")],
                  [
                    "Branch",
                    profile.scopes.some((s) => !s.branch_name) ? "All authorised branches" : [...new Set(profile.scopes.map((s) => s.branch_name))].join(", "),
                  ],
                ]}
              />
            </Section>
            <NotificationPreferences />
            <Section
              title="Devices & sessions"
              actions={
                profile.devices.length > 1 && (
                  <ConfirmDialog
                    title="Sign out other devices?"
                    consequence="Every other device is signed out now. You stay signed in here."
                    confirmLabel="Sign out others"
                    onConfirm={async () => void (await signOutOthers.mutateAsync())}
                  >
                    <Button variant="outline" size="sm">
                      Sign out other devices
                    </Button>
                  </ConfirmDialog>
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
                      <Tag tone="success">Active</Tag>
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
                  ["Password", profile.password_changed_at ? `Set by you · last changed ${fmtDate(profile.password_changed_at)}` : "Set by you at activation"],
                  ["Recovery", "A Super Admin resets a staff password."],
                  ["MFA", "Not Configured"],
                  ["Last sign-in", fmtDateTime(profile.last_login_at)],
                ]}
              />
              <div className="mt-3">
                <Button variant="outline" asChild>
                  <Link to="/change-password">Change password</Link>
                </Button>
              </div>
              <div className="mt-3">
                <Note>Only you know your password; a Super Admin can reset it if you are locked out.</Note>
              </div>
            </Section>
          </>
        )}
      </QueryView>
    </div>
  );
}
