import { useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { Ban, LinkIcon, LogOut, RotateCcw } from "lucide-react";
import { adminApi, adminKeys, type ActivationIssued, type StudentAccount, type StudentFilters } from "@/api/admin";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { ConfirmAction, DataTable, KeyValue, Note, PageHead, QueryView, Section, StatusBadge, type Tone } from "@/components/lms/ui";
import { useApiMutation } from "@/lib/mutation";
import { FilterField, FormDialog, Pager, SecretDialog } from "./shared";
import { istDateTime, useCanAdminister } from "./format";

const ACTIVATION_STATUSES = ["Account Created", "Activation Pending", "Activated", "Suspended"] as const;
// Where the student's outstanding activation link came from. The CRM does not deliver its link yet, so a student whose
// link is from CRM provisioning can only activate once a coordinator or Super Admin issues a new one.
const ACTIVATION_CHANNELS = [
  { value: "CRM provisioning", label: "CRM provisioning (not delivered)" },
  { value: "Staff issued", label: "Staff issued" },
];
const ACTIVATION_TONE: Record<StudentAccount["activation_status"], Tone> = {
  "Account Created": "neutral",
  "Activation Pending": "warning",
  Activated: "success",
  Suspended: "danger",
};

const enrolmentSummary = (counts: Record<string, number>) =>
  Object.entries(counts)
    .map(([status, n]) => `${n} ${status}`)
    .join(" · ") || "No enrolments";

/** Student Accounts: search, activation status, LMS login and enrolments; activation links, suspension and sessions. */
export function AdminStudents() {
  const [filters, setFilters] = useState<StudentFilters>({});
  const [openId, setOpenId] = useState<number | null>(null);
  const query = useQuery({ queryKey: adminKeys.students(filters), queryFn: () => adminApi.students(filters) });

  return (
    <>
      <PageHead
        title="Student Accounts"
        description="Search by Student ID, name or email. Students and their logins are created by the CRM (Admission Qualified), never here."
      />
      <div className="space-y-4">
        <Section>
          <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <FilterField label="Student ID, name or email">
              <Input aria-label="Student ID, name or email" value={filters.q ?? ""} onChange={(e) => setFilters({ ...filters, q: e.target.value, page: 1 })} />
            </FilterField>
            <FilterField label="Activation status">
              <NativeSelect
                aria-label="Activation status"
                placeholder="All"
                value={filters.activation_status ?? ""}
                options={ACTIVATION_STATUSES.map((s) => ({ value: s, label: s }))}
                onChange={(e) => setFilters({ ...filters, activation_status: e.target.value, page: 1 })}
              />
            </FilterField>
            <FilterField label="Activation link from">
              <NativeSelect
                aria-label="Activation link from"
                placeholder="Any"
                value={filters.activation_channel ?? ""}
                options={ACTIVATION_CHANNELS}
                onChange={(e) => setFilters({ ...filters, activation_channel: e.target.value, page: 1 })}
              />
            </FilterField>
          </div>
          <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No students match.">
            {(page) => (
              <>
                <DataTable
                  caption="Students"
                  rows={page.data}
                  getKey={(s) => s.student_id}
                  cols={[
                    {
                      h: "Student",
                      c: (s) => (
                        <>
                          <div className="font-medium">{s.full_name}</div>
                          <div className="font-mono text-xs text-muted-foreground">{s.student_code}</div>
                          {s.email && <div className="text-xs text-muted-foreground">{s.email}</div>}
                        </>
                      ),
                    },
                    { h: "Branch", c: (s) => s.service_branch.branch_code },
                    { h: "Activation", c: (s) => <StatusBadge tone={ACTIVATION_TONE[s.activation_status]}>{s.activation_status}</StatusBadge> },
                    {
                      h: "LMS account",
                      c: (s) => (
                        <>
                          <div className="font-mono text-xs">{s.lms_user_id}</div>
                          <div className="text-xs text-muted-foreground">
                            {s.user_id === null ? "No login" : s.is_login_active ? "Login active" : "Login blocked"} · {s.active_sessions} session
                            {s.active_sessions === 1 ? "" : "s"}
                          </div>
                        </>
                      ),
                    },
                    { h: "Enrolments", c: (s) => <span className="text-xs">{enrolmentSummary(s.enrolment_counts)}</span> },
                    {
                      h: "Action",
                      c: (s) => (
                        <Button variant="outline" size="sm" onClick={() => setOpenId(s.student_id)} aria-label={`Open ${s.full_name}`}>
                          Open
                        </Button>
                      ),
                    },
                  ]}
                />
                <Pager meta={page.meta} onPage={(p) => setFilters({ ...filters, page: p })} />
              </>
            )}
          </QueryView>
        </Section>
        <Note>
          Branch Managers and Academic Coordinators can also issue activation links for their own branch. Suspension, session revocation and reactivation are
          Super Admin actions and are audited.
        </Note>
      </div>
      {openId !== null && <StudentPanel studentId={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}

/** The list and the open student's detail both change with any account action. */
const ACCOUNT_KEYS = () => [[...adminKeys.studentsAll], ["admin", "student"]];

function StudentPanel({ studentId, onClose }: { studentId: number; onClose: () => void }) {
  const canEdit = useCanAdminister();
  const query = useQuery({ queryKey: adminKeys.student(studentId), queryFn: () => adminApi.student(studentId) });
  const [dialog, setDialog] = useState<"suspend" | null>(null);
  const [issued, setIssued] = useState<ActivationIssued | null>(null);

  const issue = useApiMutation(() => adminApi.issueActivation(studentId), { invalidate: ACCOUNT_KEYS(), onSuccess: setIssued });
  const reactivate = useApiMutation(() => adminApi.reactivateStudent(studentId), { success: "Account reactivated", invalidate: ACCOUNT_KEYS() });
  const revoke = useApiMutation(() => adminApi.revokeStudentSessions(studentId), {
    success: (r) => `${r.sessions_ended} session${r.sessions_ended === 1 ? "" : "s"} ended`,
    invalidate: ACCOUNT_KEYS(),
  });

  return (
    <>
      <Dialog open onOpenChange={(open) => !open && onClose()}>
        <DialogContent className="max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Student account</DialogTitle>
            <DialogDescription>Identity, LMS login, enrolments and recent account history.</DialogDescription>
          </DialogHeader>
          <QueryView query={query}>
            {(s) => (
              <div className="space-y-4">
                <KeyValue
                  items={[
                    ["Student", s.full_name],
                    [
                      "Student ID",
                      <span key="id" className="font-mono">
                        {s.student_code}
                      </span>,
                    ],
                    ["Email", s.email ?? "None on record"],
                    ["Service branch", `${s.service_branch.branch_name} (${s.service_branch.branch_code})`],
                    [
                      "Activation",
                      <StatusBadge key="a" tone={ACTIVATION_TONE[s.activation_status]}>
                        {s.activation_status}
                      </StatusBadge>,
                    ],
                    [
                      "LMS account",
                      s.user_id === null ? "No login" : `${s.is_login_active ? "Active" : "Blocked"} · password ${s.has_password ? "set" : "not set"}`,
                    ],
                    ["Last sign-in", istDateTime(s.last_login_at)],
                    ["Active sessions", s.active_sessions],
                  ]}
                />
                {s.suspension && (
                  <p className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
                    Suspended {istDateTime(s.suspension.suspended_at)}: {s.suspension.reason}
                  </p>
                )}
                {s.activation && (
                  <p className="text-sm text-muted-foreground">
                    Activation link {s.activation.status} · issued {istDateTime(s.activation.issued_at)} ({s.activation.channel}) · expires{" "}
                    {istDateTime(s.activation.expires_at)}
                  </p>
                )}
                {canEdit && (
                  <div className="flex flex-wrap gap-2">
                    {s.activation_status !== "Activated" && s.activation_status !== "Suspended" && (
                      <Button variant="outline" size="sm" onClick={() => issue.mutate()} disabled={issue.isPending}>
                        <LinkIcon className="size-3.5" /> {s.activation ? "Reissue activation link" : "Issue activation link"}
                      </Button>
                    )}
                    {s.activation_status === "Suspended" ? (
                      <Button variant="outline" size="sm" onClick={() => reactivate.mutate()} disabled={reactivate.isPending}>
                        <RotateCcw className="size-3.5" /> Reactivate account
                      </Button>
                    ) : (
                      <Button variant="outline" size="sm" onClick={() => setDialog("suspend")}>
                        <Ban className="size-3.5" /> Suspend account
                      </Button>
                    )}
                    {s.user_id !== null && (
                      <ConfirmAction
                        title="Sign this student out everywhere?"
                        description="Every active session ends. The student can sign in again."
                        confirmLabel="Revoke sessions"
                        onConfirm={() => revoke.mutateAsync().then(() => undefined)}
                      >
                        <Button variant="outline" size="sm">
                          <LogOut className="size-3.5" /> Revoke sessions
                        </Button>
                      </ConfirmAction>
                    )}
                  </div>
                )}
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Enrolments</h3>
                  <DataTable
                    caption="Enrolments"
                    rows={s.enrolments}
                    getKey={(e) => e.enrolment_id}
                    empty="No enrolments."
                    cols={[
                      { h: "Enrolment", c: (e) => <span className="font-mono text-xs">{e.enrolment_code}</span> },
                      { h: "Course", c: (e) => `${e.course_title} (${e.course_code})` },
                      { h: "Kind", c: (e) => e.kind },
                      { h: "Status", c: (e) => <StatusBadge>{e.status}</StatusBadge> },
                    ]}
                  />
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Recent account history</h3>
                  {s.audit.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No account actions yet.</p>
                  ) : (
                    <ul className="space-y-1 text-sm">
                      {s.audit.map((a) => (
                        <li key={a.audit_id}>
                          <span className="font-medium">{a.action}</span> · {istDateTime(a.occurred_at)}
                          {a.reason && ` · ${a.reason}`}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </QueryView>
        </DialogContent>
      </Dialog>
      {dialog === "suspend" && <SuspendDialog studentId={studentId} onClose={() => setDialog(null)} />}
      {issued && (
        <SecretDialog
          title="Activation link issued"
          description={`Give this link to ${issued.student_code} in person or through the branch. It works once, expires ${istDateTime(issued.expires_at)} and is shown only now.`}
          label="Activation link"
          value={`${window.location.origin}${issued.activation_path}`}
          onClose={() => setIssued(null)}
        />
      )}
    </>
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
      description="The student cannot sign in, every session ends and any outstanding activation link is cancelled."
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
