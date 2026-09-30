import { useMemo, useState } from "react";
import { attendanceApi, attendanceKeys, useCorrections, useProgressRows, useRecoveries } from "@/api/attendance";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, Note, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AttendanceCell, FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate, percent } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";

function RecoveryQueue() {
  const query = useRecoveries({ status: "Requested" });
  const decide = useApiMutation(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string; target?: string }) =>
      attendanceApi.decideRecovery(v.id, { decision: v.decision, decision_note: v.note, target_date: v.target || undefined }),
    {
      success: (r) => `${r.recovery_code} ${r.status.toLowerCase()}.`,
      invalidate: [attendanceKeys.all, ["progress"]],
    },
  );
  return (
    <Section title="Recovery requests">
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No recovery is waiting for a decision.">
        {(page) => (
          <DataTable
            caption="Recovery requests"
            rows={page.data}
            getKey={(r) => r.recovery_id}
            cols={[
              { h: "Code", c: (r) => r.recovery_code },
              { h: "Student", c: (r) => r.student.full_name },
              { h: "Missed class", c: (r) => `${r.session.title} · ${fmtDate(r.session.starts_at)}` },
              { h: "Method", c: (r) => r.method },
              { h: "Reason", c: (r) => r.reason },
              {
                h: "Decision",
                c: (r) => (
                  <div className="flex flex-wrap gap-2">
                    <FormDialog
                      trigger={<Button size="sm">Approve</Button>}
                      title={`Approve ${r.recovery_code}`}
                      submitLabel="Approve recovery"
                      fields={[
                        { name: "target", label: "Complete by", kind: "date" },
                        { name: "note", label: "Note to the student", kind: "textarea" },
                      ]}
                      onSubmit={(v) => decide.mutateAsync({ id: r.recovery_id, decision: "Approved", note: v["note"] || undefined, target: v["target"] })}
                    />
                    <FormDialog
                      trigger={
                        <Button size="sm" variant="outline">
                          Reject
                        </Button>
                      }
                      title={`Reject ${r.recovery_code}`}
                      submitLabel="Reject"
                      fields={[{ name: "note", label: "Reason", kind: "textarea", required: true }]}
                      onSubmit={(v) => decide.mutateAsync({ id: r.recovery_id, decision: "Rejected", note: v["note"] })}
                    />
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
    </Section>
  );
}

function CorrectionQueue() {
  const query = useCorrections({ status: "Pending" });
  const decide = useApiMutation(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) =>
      attendanceApi.decideCorrection(v.id, { decision: v.decision, decision_note: v.note }),
    {
      success: (c) => `Correction ${c.status.toLowerCase()}.`,
      invalidate: [attendanceKeys.all, ["progress"], ["completion"], ["certificates"]],
    },
  );
  return (
    <Section title="Attendance corrections and disputes">
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No correction is waiting for a decision.">
        {(page) => (
          <DataTable
            caption="Attendance corrections"
            rows={page.data}
            getKey={(c) => c.correction_id}
            cols={[
              { h: "Student", c: (c) => c.student.full_name },
              { h: "Class", c: (c) => `${c.session.title} · ${fmtDate(c.session.starts_at)}` },
              { h: "Change", c: (c) => `${c.previous_status ?? "Not yet marked"} → ${c.requested_status}` },
              { h: "Reason", c: (c) => `${c.reason} (${c.requested_by.full_name})` },
              {
                h: "Decision",
                c: (c) => (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" disabled={decide.isPending} onClick={() => decide.mutate({ id: c.correction_id, decision: "Approved" })}>
                      Approve
                    </Button>
                    <FormDialog
                      trigger={
                        <Button size="sm" variant="outline">
                          Reject
                        </Button>
                      }
                      title="Reject correction"
                      submitLabel="Reject"
                      fields={[{ name: "note", label: "Reason", kind: "textarea", required: true }]}
                      onSubmit={(v) => decide.mutateAsync({ id: c.correction_id, decision: "Rejected", note: v["note"] })}
                    />
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <p className="mt-2 text-xs text-muted-foreground">
        The reviewer must not be the requester or the person who marked the entry; approvals need fresh sign-in.
      </p>
    </Section>
  );
}

export function AcademicProgress() {
  const [q, setQ] = useState("");
  const [batch, setBatch] = useState("");
  const [alertsOnly, setAlertsOnly] = useState(false);
  const query = useProgressRows({ per_page: 100 });
  const batches = useMemo(() => [...new Set((query.data?.data ?? []).flatMap((r) => (r.batch ? [r.batch.batch_code] : [])))], [query.data]);

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHead title="Attendance & Progress" description="Four separate measures per student · attendance alert threshold from settings" />
      <div className="flex flex-wrap items-center gap-3">
        <NativeSelect
          aria-label="Batch"
          className="w-64"
          value={batch}
          onChange={(e) => setBatch(e.target.value)}
          placeholder="All batches"
          options={batches.map((b) => ({ value: b, label: b }))}
        />
        <Input aria-label="Search students" className="w-56" placeholder="Search student" value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={alertsOnly} onChange={(e) => setAlertsOnly(e.target.checked)} /> Attendance alerts only
        </label>
      </div>
      <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No student is studying yet.">
        {(page) => (
          <DataTable
            caption="Progress"
            rows={page.data.filter(
              (r) =>
                (!batch || r.batch?.batch_code === batch) &&
                (!alertsOnly || r.attendance.alert) &&
                (!q || r.student.full_name.toLowerCase().includes(q.toLowerCase())),
            )}
            getKey={(r) => r.enrolment.enrolment_id}
            cols={[
              { h: "Student", c: (r) => `${r.student.full_name} (${r.enrolment.course.course_code})` },
              { h: "Batch", c: (r) => r.batch?.batch_code ?? "—" },
              { h: "Curriculum delivered", c: (r) => percent(r.delivery.percent) },
              { h: "Attendance / recovery", c: (r) => <AttendanceCell measures={r.attendance} /> },
              { h: "Required learning", c: (r) => percent(r.required_learning.percent) },
              { h: "Engagement", c: (r) => <StatusBadge>{r.engagement.level}</StatusBadge> },
            ]}
          />
        )}
      </QueryView>
      <Note>The four measures are never merged into a single completion score.</Note>
      <RecoveryQueue />
      <CorrectionQueue />
    </div>
  );
}
