/** One student's account: what to do next, the facts, the activation link, their courses and recent history. */
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Ban, LogOut, RotateCcw } from "lucide-react";
import { adminApi, adminKeys } from "@/api/admin";
import { Field, applyServerErrors } from "@/components/lms/forms";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { DataTable, KeyValue, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApiMutation } from "@/lib/mutation";
import { FormDialog } from "./shared";
import { istDateTime, useCanAdminister } from "./format";
import { ACCOUNT_KEYS, NextStepButton } from "./student-actions";

export function AdminStudentPage() {
  const { id } = useParams({ strict: false }) as { id: string };
  const studentId = Number(id);
  const canEdit = useCanAdminister();
  const query = useQuery({ queryKey: adminKeys.student(studentId), queryFn: () => adminApi.student(studentId) });
  const [suspending, setSuspending] = useState(false);
  const reactivate = useApiMutation(() => adminApi.reactivateStudent(studentId), { success: "Account reactivated", invalidate: ACCOUNT_KEYS() });
  const revoke = useApiMutation(() => adminApi.revokeStudentSessions(studentId), {
    success: (r) => `${r.sessions_ended} session${r.sessions_ended === 1 ? "" : "s"} ended`,
    invalidate: ACCOUNT_KEYS(),
  });

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <QueryView query={query} skeleton="detail">
        {(s) => (
          <>
            <Breadcrumbs items={[{ label: "Student accounts", to: "/admin/students" }, { label: s.full_name }]} />
            <PageHead title={s.full_name} description={`${s.student_code} · ${s.service_branch.branch_name}`} />

            <section
              aria-label="Suggested next step"
              className={`rounded-xl border p-4 shadow-sm sm:p-5 ${s.suggested_step.attention ? "border-warning/50 bg-warning-soft" : "bg-card"}`}
            >
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Suggested next step</p>
              <h2 className="mt-1 text-lg font-semibold">{s.suggested_step.label}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{s.suggested_step.detail}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <NextStepButton studentId={s.student_id} step={s.suggested_step} size="default" />
                {s.suggested_step.action === "send_link" && (
                  <span className="text-xs text-muted-foreground">The link goes by WhatsApp. If it cannot, you get a link to copy and pass on.</span>
                )}
              </div>
            </section>

            {s.suspension && (
              <StatusNote tone="danger">
                Suspended {istDateTime(s.suspension.suspended_at)}: {s.suspension.reason}
              </StatusNote>
            )}

            <Section title="Account">
              <KeyValue
                items={[
                  [
                    "Student ID",
                    <span key="id" className="font-mono">
                      {s.student_code}
                    </span>,
                  ],
                  ["Email", s.email ?? "None on record"],
                  ["Activation", <StatusBadge key="a" domain="account" code={s.activation_status} />],
                  [
                    "Sign-in",
                    s.user_id === null ? "No login yet" : `${s.is_login_active ? "Allowed" : "Switched off"} · password ${s.has_password ? "set" : "not set"}`,
                  ],
                  ["Last sign-in", istDateTime(s.last_login_at)],
                  ["Signed in on", `${s.active_sessions} device${s.active_sessions === 1 ? "" : "s"}`],
                ]}
              />
              {s.activation && (
                <p className="mt-3 text-sm text-muted-foreground">
                  Activation link: {s.activation.status} · sent {istDateTime(s.activation.issued_at)} · works until {istDateTime(s.activation.expires_at)}
                  {s.activation.whatsapp
                    ? ` · WhatsApp: ${s.activation.whatsapp.state.toLowerCase()}${s.activation.whatsapp.note ? ` (${s.activation.whatsapp.note})` : ""}`
                    : ""}
                </p>
              )}
            </Section>

            <Section title="Courses">
              <DataTable
                caption="Enrolments"
                rows={s.enrolments}
                getKey={(e) => e.enrolment_id}
                empty="No courses yet."
                cols={[
                  { h: "Course", c: (e) => `${e.course_title} (${e.course_code})` },
                  { h: "Kind", c: (e) => e.kind },
                  { h: "Status", c: (e) => <StatusBadge domain="enrolment" code={e.status} /> },
                ]}
              />
            </Section>

            <Section title="Recent history">
              {s.audit.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nothing has been done to this account yet.</p>
              ) : (
                <ul className="divide-y text-sm">
                  {s.audit.map((a) => (
                    <li key={a.audit_id} className="py-2">
                      <p>{a.sentence}</p>
                      <p className="text-xs text-muted-foreground">
                        {istDateTime(a.occurred_at)}
                        {a.reason ? ` · ${a.reason}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-sm">
                <Link
                  to="/admin/audit"
                  search={{ entity_type: "student", entity_id: String(s.student_id) } as never}
                  className="text-primary underline-offset-2 hover:underline"
                >
                  See everything done to this account
                </Link>
              </p>
            </Section>

            {canEdit && (
              <Section title="Other actions">
                <div className="flex flex-wrap gap-2">
                  {s.activation_status === "Suspended" ? (
                    <Button variant="outline" size="sm" onClick={() => reactivate.mutate()} disabled={reactivate.isPending}>
                      <RotateCcw className="size-3.5" aria-hidden /> Reactivate account
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" onClick={() => setSuspending(true)}>
                      <Ban className="size-3.5" aria-hidden /> Suspend account
                    </Button>
                  )}
                  {s.user_id !== null && (
                    <ConfirmDialog
                      title="Sign this student out everywhere?"
                      consequence="Every device this student is signed in on is signed out now. They can sign in again with their password."
                      confirmLabel="Sign out everywhere"
                      onConfirm={() => revoke.mutateAsync().then(() => undefined)}
                    >
                      <Button variant="outline" size="sm">
                        <LogOut className="size-3.5" aria-hidden /> Sign out everywhere
                      </Button>
                    </ConfirmDialog>
                  )}
                </div>
              </Section>
            )}
            {suspending && <SuspendDialog studentId={studentId} onClose={() => setSuspending(false)} />}
          </>
        )}
      </QueryView>
    </div>
  );
}

function SuspendDialog({ studentId, onClose }: { studentId: number; onClose: () => void }) {
  const form = useForm<{ reason: string }>({ defaultValues: { reason: "" } });
  const suspend = useApiMutation((v: { reason: string }) => adminApi.suspendStudent(studentId, v.reason), {
    success: "Account suspended",
    invalidate: ACCOUNT_KEYS(),
    onSuccess: onClose,
    silentValidation: true,
    onError: (e) => applyServerErrors(form, e),
  });
  return (
    <FormDialog
      title="Suspend account"
      description="The student cannot sign in, every device is signed out and any link they were sent stops working."
      submitLabel="Suspend"
      destructive
      onClose={onClose}
      busy={suspend.isPending}
      onSubmit={form.handleSubmit((v) => suspend.mutate(v))}
    >
      <Field label="Reason" htmlFor="suspend-reason" error={form.formState.errors.reason?.message}>
        <Input id="suspend-reason" {...form.register("reason", { required: "Give a reason for the audit log" })} />
      </Field>
    </FormDialog>
  );
}
