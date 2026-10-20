import { useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import {
  ATTENDANCE_STATUSES,
  attendanceApi,
  attendanceKeys,
  useCorrections,
  useRecoveries,
  useRegister,
  useRegisterSessions,
  type AttendanceStatus,
  type Correction,
  type RegisterRow,
  type RegisterSession,
} from "@/api/attendance";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, PageHead, PillTabs, QueryView, Section, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate, fmtRange } from "@/features/shared/format";
import { requestKeys } from "@/api/requests";
import { useApiMutation } from "@/lib/mutation";
import { cn } from "@/lib/utils";

type Draft = Record<number, { status: AttendanceStatus; remarks: string }>;

/**
 * The register for one class: used by Today's class flow and by the Attendance screen, so both save the same way.
 * The Save bar sticks to the bottom of the screen while the register is on it.
 */
export function RegisterForm({ sessionId, onSaved, heading = true }: { sessionId: number; onSaved?: () => void; heading?: boolean }) {
  const query = useRegister(sessionId);
  const [draft, setDraft] = useState<Draft>({});
  const invalidate = [attendanceKeys.all, ["progress"], ["completion"], ["trainer"], ["nav"], requestKeys.mine];
  const save = useApiMutation((body: Parameters<typeof attendanceApi.mark>[1]) => attendanceApi.mark(sessionId, body), {
    success: "Attendance saved.",
    invalidate,
    onSuccess: () => {
      setDraft({});
      onSaved?.();
    },
  });
  const correct = useApiMutation(attendanceApi.requestCorrection, {
    success: "Correction sent.",
    next: "Your Branch Manager decides. You will be told, and it shows under My requests.",
    view: { to: "/trainer/requests", label: "My requests" },
    invalidate,
  });

  return (
    <QueryView query={query} skeleton="cards">
      {(register) => {
        const effective = (row: RegisterRow) => draft[row.enrolment.enrolment_id]?.status ?? row.attendance?.status ?? null;
        const unmarked = register.rows.filter((r) => effective(r) === null).length;
        const dirty = Object.keys(draft).length > 0;
        const editable = register.can_mark && !register.locked && register.session.state !== "Scheduled";
        const excusedWithoutReason = register.rows.some(
          (r) => draft[r.enrolment.enrolment_id]?.status === "Excused" && !draft[r.enrolment.enrolment_id]?.remarks.trim(),
        );

        const pick = (row: RegisterRow, status: AttendanceStatus) =>
          setDraft({
            ...draft,
            [row.enrolment.enrolment_id]: { status, remarks: draft[row.enrolment.enrolment_id]?.remarks ?? row.attendance?.remarks ?? "" },
          });
        const confirmed = register.rows.filter((r) => r.student_confirmed_at && effective(r) === null);
        const markConfirmed = () => {
          const next: Draft = { ...draft };
          for (const row of confirmed) next[row.enrolment.enrolment_id] = { status: "Present", remarks: "Confirmed by the student" };
          setDraft(next);
        };
        const markAllPresent = () => {
          const next: Draft = { ...draft };
          for (const row of register.rows) if (effective(row) === null) next[row.enrolment.enrolment_id] = { status: "Present", remarks: "" };
          setDraft(next);
        };

        return (
          <Section title={heading ? `${register.session.title} · ${fmtDate(register.session.starts_at)}` : "Register"}>
            <p className="mb-3 text-sm text-muted-foreground">
              {register.session.batch.batch_code} · {fmtRange(register.session.starts_at, register.session.ends_at)} · {register.session.mode}{" "}
              <StatusBadge domain="session" code={register.session.state} />
            </p>
            {register.session.state === "Scheduled" && (
              <div className="mb-3">
                <StatusNote tone="info">Attendance can be marked once the class has been started.</StatusNote>
              </div>
            )}
            {register.locked && (
              <div className="mb-3">
                <StatusNote tone="warning">
                  Attendance closed {register.lock_days} days after the class. To change an entry now, send a correction; your Branch Manager decides it.
                </StatusNote>
              </div>
            )}
            {register.rows.length === 0 && <EmptyState reason="No student holds a seat in this batch yet, so there is nobody to mark." />}
            <ul className="divide-y">
              {register.rows.map((row) => {
                const current = effective(row);
                const id = row.enrolment.enrolment_id;
                return (
                  <li key={id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <div className="min-w-0">
                      <span className="text-sm font-medium">{row.student.full_name}</span>
                      <span className="ml-2 text-xs text-muted-foreground">{row.student.student_code}</span>
                      {row.recovery && (
                        <span className="ml-2">
                          <StatusBadge domain="attendance" code={row.attendance?.status ?? row.label} label={row.label} />
                        </span>
                      )}
                      {row.student_confirmed_at && effective(row) === null && (
                        <span className="ml-2">
                          <Tag tone="info">Says they attended</Tag>
                        </span>
                      )}
                      {row.correction_pending && (
                        <span className="ml-2">
                          <Tag tone="warning">Correction waiting</Tag>
                        </span>
                      )}
                    </div>
                    {editable ? (
                      <div className="flex flex-wrap items-center gap-1" role="radiogroup" aria-label={`Attendance for ${row.student.full_name}`}>
                        {ATTENDANCE_STATUSES.map((status) => (
                          <label
                            key={status}
                            className={cn(
                              "tap flex cursor-pointer items-center gap-1 rounded-lg border px-3 text-sm",
                              current === status && "border-primary bg-accent font-semibold",
                            )}
                          >
                            <input type="radio" className="sr-only" name={`att-${id}`} checked={current === status} onChange={() => pick(row, status)} />
                            {current === status ? "✓ " : ""}
                            {status}
                          </label>
                        ))}
                        {draft[id]?.status === "Excused" && (
                          <Input
                            aria-label={`Approved reason for ${row.student.full_name}`}
                            className="w-48"
                            placeholder="Approved reason"
                            value={draft[id]?.remarks ?? ""}
                            onChange={(e) => setDraft({ ...draft, [id]: { status: "Excused", remarks: e.target.value } })}
                          />
                        )}
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <StatusBadge domain="attendance" code={current ?? "Not yet marked"} />
                        {register.can_mark && !row.correction_pending && register.session.state !== "Scheduled" && (
                          <FormDialog
                            trigger={
                              <Button size="sm" variant="ghost">
                                Ask for a correction
                              </Button>
                            }
                            title={`Correct attendance: ${row.student.full_name}`}
                            description="Your Branch Manager decides this. You will be told, and it shows under My requests."
                            submitLabel="Send request"
                            fields={[
                              { name: "status", label: "It should say", kind: "select", options: ATTENDANCE_STATUSES.filter((s) => s !== current) },
                              { name: "reason", label: "Why", kind: "textarea", required: true },
                            ]}
                            onSubmit={(v) =>
                              correct.mutateAsync({
                                session_id: sessionId,
                                enrolment_id: id,
                                requested_status: v["status"] as AttendanceStatus,
                                reason: v["reason"]!,
                              })
                            }
                          />
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
            {editable && register.rows.length > 0 && (
              <div
                className="sticky bottom-[4.5rem] z-10 -mx-4 mt-3 flex flex-wrap items-center justify-between gap-3 border-t bg-card px-4 py-3 md:bottom-0"
                data-testid="save-bar"
              >
                <p className="text-sm" aria-live="polite">
                  {unmarked > 0 ? `${unmarked} of ${register.rows.length} not marked yet` : "Everyone is marked"}
                  {dirty && <span className="text-muted-foreground"> · changes not saved</span>}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  {confirmed.length > 0 && (
                    <Button variant="outline" onClick={markConfirmed}>
                      Mark the {confirmed.length} who confirmed Present
                    </Button>
                  )}
                  <Button variant="outline" onClick={markAllPresent} disabled={unmarked === 0}>
                    Mark everyone else Present
                  </Button>
                  <Button
                    disabled={!dirty || excusedWithoutReason || save.isPending}
                    onClick={() =>
                      save.mutate({
                        entries: Object.entries(draft).map(([enrolment_id, d]) => ({
                          enrolment_id: Number(enrolment_id),
                          status: d.status,
                          remarks: d.remarks.trim() || null,
                        })),
                      })
                    }
                  >
                    Save attendance
                  </Button>
                </div>
              </div>
            )}
          </Section>
        );
      }}
    </QueryView>
  );
}

function RecoveriesToVerify() {
  const query = useRecoveries({ status: "Approved" });
  const complete = useApiMutation((v: { id: number; note: string }) => attendanceApi.completeRecovery(v.id, v.note), {
    success: "Recovery marked as done.",
    next: "The student is told.",
    invalidate: [attendanceKeys.all, ["progress"], ["nav"]],
  });
  return (
    <QueryView
      query={query}
      isEmpty={(page) => page.data.length === 0}
      empty="No recovery is waiting for you to check. Approved recoveries show here once the student has done the work."
    >
      {(page) => (
        <DataTable
          caption="Recoveries to verify"
          rows={page.data}
          getKey={(r) => r.recovery_id}
          cols={[
            { h: "Student", c: (r) => r.student.full_name },
            { h: "Missed class", c: (r) => `${r.session.title} · ${fmtDate(r.session.starts_at)}` },
            { h: "How they make it up", c: (r) => r.method },
            { h: "Agreed date", c: (r) => fmtDate(r.target_date) },
            {
              h: "",
              c: (r) => (
                <FormDialog
                  trigger={<Button size="sm">Check and mark done</Button>}
                  title={`Recovery for ${r.student.full_name}`}
                  description="A recording link or the student's word alone is not proof. Say what you checked."
                  submitLabel="Mark as done"
                  fields={[{ name: "note", label: "What you checked", kind: "textarea", required: true }]}
                  onSubmit={(v) => complete.mutateAsync({ id: r.recovery_id, note: v["note"]! })}
                />
              ),
            },
          ]}
        />
      )}
    </QueryView>
  );
}

const TABS = ["Classes to mark", "Corrections waiting", "Recoveries to check", "Recent classes"] as const;
type Tab = (typeof TABS)[number];

function openRegisterLink(sessionId: number, label: string) {
  return (
    <Button asChild size="sm" variant="outline">
      <Link to="/trainer/attendance" search={{ session: sessionId }}>
        {label}
      </Link>
    </Button>
  );
}

function CorrectionsWaiting({ rows }: { rows: Correction[] }) {
  if (rows.length === 0)
    return (
      <EmptyState
        reason="No correction is waiting for a decision. When you ask for one, it shows here until your Branch Manager decides."
        action={
          <Button asChild size="sm" variant="outline">
            <Link to="/trainer/requests">See decided requests</Link>
          </Button>
        }
      />
    );
  return (
    <DataTable
      caption="Corrections waiting for a decision"
      rows={rows}
      getKey={(c) => c.correction_id}
      cols={[
        { h: "Student", c: (c) => c.student.full_name },
        { h: "Class", c: (c) => `${c.session.title} · ${fmtDate(c.session.starts_at)}` },
        { h: "Change", c: (c) => `${c.previous_status ?? "Not marked"} to ${c.requested_status}` },
        { h: "Why", c: (c) => c.reason },
        { h: "Asked by", c: (c) => c.requested_by.full_name },
        { h: "Who decides", c: () => "Your Branch Manager" },
        { h: "", c: (c) => openRegisterLink(c.session.session_id, "Open register") },
      ]}
    />
  );
}

function RegisterPage({ sessionId }: { sessionId: number }) {
  const navigate = useNavigate();
  const register = useRegister(sessionId);
  const title = register.data?.session.title ?? "Class";
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Breadcrumbs items={[{ label: "Attendance", to: "/trainer/attendance" }, { label: title }]} />
      <PageHead title="Mark attendance" description="Mark each student, then save. You can come back to finish later." />
      <RegisterForm sessionId={sessionId} heading />
      <div>
        <Button variant="outline" onClick={() => void navigate({ to: "/trainer/attendance", search: {} })}>
          Back to the list
        </Button>
      </div>
    </div>
  );
}

export function TrainerAttendance() {
  const { session } = useSearch({ from: "/trainer/attendance" });
  const [tab, setTab] = useState<Tab | null>(null);
  const toMark = useRegisterSessions({ attendance: "pending", per_page: 50 });
  const corrections = useCorrections({ status: "Pending", per_page: 50 });
  const recoveries = useRecoveries({ status: "Approved" });
  const recent = useRegisterSessions({ per_page: 30 });

  if (session) return <RegisterPage sessionId={session} />;

  const counts: Record<Tab, number> = {
    "Classes to mark": toMark.data?.meta.total ?? 0,
    "Corrections waiting": corrections.data?.meta.total ?? 0,
    "Recoveries to check": recoveries.data?.meta.total ?? 0,
    "Recent classes": 0,
  };
  const ready = !toMark.isPending && !corrections.isPending && !recoveries.isPending;
  // Opens on what needs doing: the first list with something in it
  const active: Tab = tab ?? (ready ? (TABS.find((t) => counts[t] > 0) ?? "Classes to mark") : "Classes to mark");

  const rowAction = (s: RegisterSession) => openRegisterLink(s.session_id, s.attendance_state === "Marked" || s.locked ? "Open register" : "Mark attendance");
  const classRows = (query: typeof toMark, empty: string) => (
    <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty={empty}>
      {(page) => (
        <DataTable
          caption="Classes"
          rows={page.data}
          getKey={(s) => s.session_id}
          cols={[
            { h: "When", c: (s) => `${fmtDate(s.starts_at)} · ${fmtRange(s.starts_at, s.ends_at)}` },
            { h: "Class", c: (s) => s.title },
            { h: "Batch", c: (s) => s.batch.batch_code },
            { h: "Marked", c: (s) => `${s.marked} of ${s.seats} students` },
            { h: "Status", c: (s) => <StatusBadge domain={s.locked ? "session" : "attendance"} code={s.locked ? "Locked" : s.attendance_state} /> },
            { h: "", c: rowAction },
          ]}
        />
      )}
    </QueryView>
  );

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead title="Unmarked & corrections" description="Mark the classes still waiting, follow up corrections and check recoveries." />
      <PillTabs label="Attendance work" tabs={TABS} value={active} onChange={setTab} counts={counts} />
      {active === "Classes to mark" &&
        classRows(toMark, "Every class you have held is marked. Classes show here once they have started and some students are still unmarked.")}
      {active === "Corrections waiting" &&
        (corrections.isPending ? <QueryView query={corrections}>{() => null}</QueryView> : <CorrectionsWaiting rows={corrections.data?.data ?? []} />)}
      {active === "Recoveries to check" && <RecoveriesToVerify />}
      {active === "Recent classes" && classRows(recent, "No class has been held yet.")}
      <HowThisWorks>
        <p>
          Attendance for a class can be marked from the moment it starts. It closes some days after the class (the register says when): to change an entry after
          that, send a correction. Your Branch Manager decides corrections, and the answer appears under My requests.
        </p>
        <p>A recovery is a make-up for a missed class. Your Branch Manager approves it; you check that the student did the work, then mark it done.</p>
      </HowThisWorks>
    </div>
  );
}
