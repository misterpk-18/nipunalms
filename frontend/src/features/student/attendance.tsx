import {
  attendanceApi,
  attendanceKeys,
  ATTENDANCE_STATUSES,
  RECOVERY_METHODS,
  useMyAttendance,
  type StudentAttendance,
  type StudentAttendanceRow,
} from "@/api/attendance";
import { DataTable, Note, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { useApiMutation } from "@/lib/mutation";
import { useT } from "@/lib/i18n";
import { AttendanceCell, FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate, fmtRange } from "@/features/shared/format";

function AttendanceTable({ block }: { block: StudentAttendance }) {
  const invalidate = [attendanceKeys.all, ["progress"]];
  const recover = useApiMutation(attendanceApi.requestRecovery, { success: "Recovery requested. Your coordinator will decide.", invalidate });
  const correct = useApiMutation(attendanceApi.requestCorrection, { success: "Correction requested. An independent reviewer will decide.", invalidate });

  const actions = (row: StudentAttendanceRow) => (
    <div className="flex flex-wrap gap-2">
      {row.can_request_recovery && row.attendance_id !== null && (
        <FormDialog
          trigger={
            <Button size="sm" variant="outline">
              Request recovery
            </Button>
          }
          title="Request recovery"
          description={`${row.session.title}: an approved recovery is reported separately; your absence is never rewritten.`}
          submitLabel="Request recovery"
          fields={[
            { name: "method", label: "How will you recover?", kind: "select", options: RECOVERY_METHODS },
            { name: "reason", label: "Reason", kind: "textarea", required: true },
          ]}
          onSubmit={(v) => recover.mutateAsync({ attendance_id: row.attendance_id!, method: v["method"]!, reason: v["reason"]! })}
        />
      )}
      {row.correction_pending ? (
        <StatusBadge tone="warning">Correction pending</StatusBadge>
      ) : (
        <FormDialog
          trigger={
            <Button size="sm" variant="ghost">
              Dispute
            </Button>
          }
          title="Request an attendance correction"
          description={`${row.session.title} · ${fmtDate(row.session.starts_at)}. Currently: ${row.label}.`}
          submitLabel="Send request"
          fields={[
            { name: "status", label: "It should say", kind: "select", options: ATTENDANCE_STATUSES.filter((s) => s !== row.status) },
            { name: "reason", label: "Reason", kind: "textarea", required: true, hint: "Requests within 7 days of publication are easiest to verify." },
          ]}
          onSubmit={(v) =>
            correct.mutateAsync({
              session_id: row.session.session_id,
              enrolment_id: block.enrolment.enrolment_id,
              requested_status: v["status"] as (typeof ATTENDANCE_STATUSES)[number],
              reason: v["reason"]!,
            })
          }
        />
      )}
    </div>
  );

  return (
    <Section title={`${block.enrolment.course.course_code} · ${block.enrolment.course.title}`}>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <span>Attendance:</span>
        <AttendanceCell measures={block.summary} />
        <span className="text-muted-foreground">Joining Date: {fmtDate(block.joining_date)}</span>
      </div>
      <DataTable
        caption="Attendance"
        rows={block.rows}
        getKey={(r) => r.session.session_id}
        empty="No class has been held for you yet."
        cols={[
          { h: "Date", c: (r) => `${fmtDate(r.session.starts_at)} · ${fmtRange(r.session.starts_at, r.session.ends_at)}` },
          { h: "Session", c: (r) => r.session.title },
          { h: "Trainer", c: (r) => r.session.trainer.full_name },
          { h: "State", c: (r) => <StatusBadge>{r.label}</StatusBadge> },
          { h: "Action", c: actions },
        ]}
      />
    </Section>
  );
}

export function Attendance() {
  const t = useT();
  const query = useMyAttendance();
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead title={t("attendance")} description="Per actual Class Session · trainer-confirmed attendance (LMS)" />
      <QueryView query={query} isEmpty={(blocks) => blocks.length === 0} empty="Attendance appears once you are allocated to a batch.">
        {(blocks) => blocks.map((block) => <AttendanceTable key={block.enrolment.enrolment_id} block={block} />)}
      </QueryView>
      <Note>
        Joining Date is the first confirmed regular-class attendance (demo classes excluded). A class that is not marked stays "Not yet marked", never an
        assumed absence.
      </Note>
    </div>
  );
}
