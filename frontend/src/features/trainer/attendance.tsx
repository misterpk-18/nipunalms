import { useState } from "react";
import {
  ATTENDANCE_STATUSES,
  attendanceApi,
  attendanceKeys,
  useRecoveries,
  useRegister,
  useRegisterSessions,
  type AttendanceStatus,
  type RegisterRow,
  type RegisterSession,
} from "@/api/attendance";
import { DataTable, PageHead, PillTabs, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate, fmtRange } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { cn } from "@/lib/utils";

type Draft = Record<number, { status: AttendanceStatus; remarks: string }>;

/** The register for one class. `onSaved` lets another screen (Today's flow) refresh what it shows after attendance is confirmed. */
export function RegisterForm({ sessionId, onSaved }: { sessionId: number; onSaved?: () => void }) {
  const query = useRegister(sessionId);
  const [draft, setDraft] = useState<Draft>({});
  const invalidate = [attendanceKeys.all, ["progress"], ["completion"]];
  const save = useApiMutation((body: Parameters<typeof attendanceApi.mark>[1]) => attendanceApi.mark(sessionId, body), {
    success: "Attendance confirmed.",
    invalidate,
    onSuccess: () => {
      setDraft({});
      onSaved?.();
    },
  });
  const correct = useApiMutation(attendanceApi.requestCorrection, { success: "Correction requested. An independent reviewer will decide.", invalidate });

  return (
    <QueryView query={query}>
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
        const markAllPresent = () => {
          const next: Draft = { ...draft };
          for (const row of register.rows) if (effective(row) === null) next[row.enrolment.enrolment_id] = { status: "Present", remarks: "" };
          setDraft(next);
        };

        return (
          <Section title={`${register.session.title} · ${fmtDate(register.session.starts_at)}`}>
            <p className="mb-3 text-sm text-muted-foreground">
              {register.session.batch.batch_code} · {fmtRange(register.session.starts_at, register.session.ends_at)} · {register.session.mode} ·{" "}
              {register.session.state}
            </p>
            {register.locked && (
              <div className="mb-3">
                <StatusNote state="Confirmation Pending">
                  Attendance locked {register.lock_days} days after the class. Changes need a correction that an independent reviewer approves.
                </StatusNote>
              </div>
            )}
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
                          <StatusBadge>{row.label}</StatusBadge>
                        </span>
                      )}
                      {row.correction_pending && (
                        <span className="ml-2">
                          <StatusBadge tone="warning">Correction pending</StatusBadge>
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
                        <StatusBadge>{current ? `${current} (trainer-confirmed)` : "Not yet marked"}</StatusBadge>
                        {register.can_mark && !row.correction_pending && (
                          <FormDialog
                            trigger={
                              <Button size="sm" variant="ghost">
                                Request correction
                              </Button>
                            }
                            title={`Correct attendance: ${row.student.full_name}`}
                            description="An independent reviewer (not you) approves this change."
                            submitLabel="Send request"
                            fields={[
                              { name: "status", label: "It should say", kind: "select", options: ATTENDANCE_STATUSES.filter((s) => s !== current) },
                              { name: "reason", label: "Reason", kind: "textarea", required: true },
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
            {editable && (
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <Button variant="outline" onClick={markAllPresent} disabled={unmarked === 0}>
                  Mark all Present
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
                  Confirm attendance
                </Button>
                {unmarked > 0 ? (
                  <StatusNote state="Not Submitted">{unmarked} student(s) not yet marked.</StatusNote>
                ) : (
                  <StatusNote state="Saved">Every seat is marked. Meet attendance evidence: Integration Unavailable.</StatusNote>
                )}
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
    success: "Recovery verified.",
    invalidate: [attendanceKeys.all, ["progress"]],
  });
  return (
    <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No approved recovery waiting for verification.">
      {(page) => (
        <DataTable
          caption="Recoveries to verify"
          rows={page.data}
          getKey={(r) => r.recovery_id}
          cols={[
            { h: "Code", c: (r) => r.recovery_code },
            { h: "Student", c: (r) => r.student.full_name },
            { h: "Missed class", c: (r) => `${r.session.title} · ${fmtDate(r.session.starts_at)}` },
            { h: "Method", c: (r) => r.method },
            { h: "Target date", c: (r) => fmtDate(r.target_date) },
            {
              h: "Action",
              c: (r) => (
                <FormDialog
                  trigger={
                    <Button size="sm" variant="outline">
                      Verify complete
                    </Button>
                  }
                  title={`Verify ${r.recovery_code}`}
                  description="A recording link or self-declaration alone is not evidence."
                  submitLabel="Mark completed"
                  fields={[{ name: "note", label: "Evidence reviewed", kind: "textarea", required: true }]}
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

export function TrainerAttendance() {
  const [tab, setTab] = useState<"Pending" | "All">("Pending");
  const [selected, setSelected] = useState<number | null>(null);
  const query = useRegisterSessions(tab === "Pending" ? { attendance: "pending", per_page: 50 } : { per_page: 50 });

  const pick = (session: RegisterSession) => (
    <Button size="sm" variant={selected === session.session_id ? "default" : "outline"} onClick={() => setSelected(session.session_id)}>
      {session.attendance_state === "Marked" || session.locked ? "Open register" : "Mark attendance"}
    </Button>
  );

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead title="Attendance register" description="Trainer-confirmed attendance for each actual Class Session." />
      <PillTabs label="Sessions" tabs={["Pending", "All"] as const} value={tab} onChange={setTab} />
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty={tab === "Pending" ? "Every class is marked." : "No class has been held yet."}>
        {(page) => (
          <DataTable
            caption="Class sessions"
            rows={page.data}
            getKey={(s) => s.session_id}
            cols={[
              { h: "Date", c: (s) => `${fmtDate(s.starts_at)} · ${fmtRange(s.starts_at, s.ends_at)}` },
              { h: "Session", c: (s) => s.title },
              { h: "Batch", c: (s) => s.batch.batch_code },
              { h: "Marked", c: (s) => `${s.marked} of ${s.seats}` },
              { h: "State", c: (s) => <StatusBadge>{s.locked ? "Locked" : s.attendance_state}</StatusBadge> },
              { h: "Action", c: pick },
            ]}
          />
        )}
      </QueryView>
      {selected !== null && <RegisterForm key={selected} sessionId={selected} />}
      <Section title="Recoveries to verify">
        <RecoveriesToVerify />
      </Section>
    </div>
  );
}
