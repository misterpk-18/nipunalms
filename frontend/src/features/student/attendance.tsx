/** My Progress, Attendance tab: each class with its status, and what the student can ask for. */
import { useState } from "react";
import { MoreHorizontal } from "lucide-react";
import {
  attendanceApi,
  attendanceKeys,
  ATTENDANCE_STATUSES,
  RECOVERY_METHODS,
  useMyAttendance,
  type CorrectionStatus,
  type RecoveryStatus,
  type StudentAttendance,
  type StudentAttendanceRow,
} from "@/api/attendance";
import { DataTable, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate, fmtRange, percent } from "@/features/shared/format";
import { useT, type TranslationKey } from "@/lib/i18n";
import { useApiMutation } from "@/lib/mutation";

type T = ReturnType<typeof useT>;

const METHOD_KEY: Record<(typeof RECOVERY_METHODS)[number], TranslationKey> = {
  "Recording watched": "recoveryRecording",
  "Extra session": "recoveryExtra",
  Assignment: "recoveryAssignment",
};

/** One request the student made, as a status badge and one line saying who decides or what they said. */
function RequestLine({ label, status, note, extra }: { label: string; status: string; note: string | null; extra?: string | null }) {
  const t = useT();
  const waiting = status === "Requested" || status === "Pending";
  return (
    <div className="space-y-0.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs font-medium">{label}</span>
        <StatusBadge domain="approval" code={status} />
      </div>
      <p className="text-xs text-muted-foreground">{waiting ? t("decidesBm") : t("decidedByBm")}</p>
      {extra && <p className="text-xs text-muted-foreground">{extra}</p>}
      {note && <p className="text-xs text-muted-foreground">{t("decisionNote", { note })}</p>}
    </div>
  );
}

function RequestCell({ recovery, correction }: { recovery: RecoveryStatus | null; correction: CorrectionStatus | null }) {
  const t = useT();
  if (!recovery && !correction) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="space-y-2">
      {recovery && (
        <RequestLine
          label={t("recoveryRequestLabel")}
          status={recovery.status}
          note={recovery.decision_note}
          extra={recovery.status === "Approved" && recovery.target_date ? t("recoverBy", { date: fmtDate(recovery.target_date) }) : null}
        />
      )}
      {correction && (
        <RequestLine
          label={t("mistakeRequestLabel")}
          status={correction.status}
          note={correction.decision_note}
          extra={correction.status === "Pending" ? t("wantedStatus", { status: statusText(correction.requested_status, t) }) : null}
        />
      )}
    </div>
  );
}

const STATUS_KEY: Record<string, TranslationKey> = { Present: "st_att_present", Absent: "st_att_absent", Late: "st_att_late", Excused: "st_att_excused" };
const statusText = (status: string, t: T) => (STATUS_KEY[status] ? t(STATUS_KEY[status]) : status);

function AttendanceTable({ block }: { block: StudentAttendance }) {
  const t = useT();
  const invalidate = [attendanceKeys.all, ["progress"]];
  const recover = useApiMutation(attendanceApi.requestRecovery, { success: t("recoverySent"), next: t("recoverySentNext"), invalidate });
  const correct = useApiMutation(attendanceApi.requestCorrection, { success: t("mistakeSent"), next: t("mistakeSentNext"), invalidate });
  const [reporting, setReporting] = useState<StudentAttendanceRow | null>(null);
  const summary = block.summary;

  const actions = (row: StudentAttendanceRow) => (
    <div className="flex flex-wrap items-center gap-1">
      {row.can_request_recovery && row.attendance_id !== null && (
        <FormDialog
          trigger={
            <Button size="sm" variant="outline" className="tap">
              {t("requestRecovery")}
            </Button>
          }
          title={t("recoveryTitle")}
          description={t("recoveryDesc", { title: row.session.title })}
          submitLabel={t("requestRecovery")}
          fields={[
            {
              name: "method",
              label: t("recoveryHow"),
              kind: "select",
              options: RECOVERY_METHODS,
              optionLabels: Object.fromEntries(RECOVERY_METHODS.map((m) => [m, t(METHOD_KEY[m])])),
            },
            { name: "reason", label: t("reasonLabel"), kind: "textarea", required: true },
          ]}
          onSubmit={(v) => recover.mutateAsync({ attendance_id: row.attendance_id!, method: v["method"]!, reason: v["reason"]! })}
        />
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="icon" variant="ghost" className="tap" aria-label={t("moreActionsFor", { title: row.session.title })}>
            <MoreHorizontal className="size-4" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem disabled={row.correction_pending} onSelect={() => setReporting(row)}>
            {t("reportMistake")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );

  return (
    <Section title={`${block.enrolment.course.course_code} · ${block.enrolment.course.title}`}>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <span>{t("measureAttendance")}:</span>
          {summary.state === "Not started" || summary.state === "Partial Data" ? (
            <StatusBadge domain="attendance" code={summary.state} />
          ) : (
            <strong>{percent(summary.percent)}</strong>
          )}
          {summary.alert && <Tag tone="danger">{t("attendanceLow", { n: summary.alert_threshold })}</Tag>}
        </span>
        <span className="text-muted-foreground">
          {block.joining_date ? t("joiningDateLine", { date: fmtDate(block.joining_date) }) : t("joiningDatePending")}
        </span>
      </div>
      <DataTable
        caption={t("attendance")}
        rows={block.rows}
        getKey={(r) => r.session.session_id}
        empty={t("noClassesYet")}
        cols={[
          { h: t("colDate"), c: (r) => `${fmtDate(r.session.starts_at)} · ${fmtRange(r.session.starts_at, r.session.ends_at)}` },
          { h: t("colClass"), c: (r) => r.session.title },
          { h: t("colTrainer"), c: (r) => r.session.trainer.full_name },
          { h: t("colStatus"), c: (r) => <StatusBadge domain="attendance" code={r.status ?? "Not yet marked"} /> },
          { h: t("colRequest"), c: (r) => <RequestCell recovery={r.recovery} correction={r.correction} /> },
          { h: t("colActions"), c: actions },
        ]}
      />
      {reporting && (
        <FormDialog
          open
          onOpenChange={(open) => !open && setReporting(null)}
          title={t("mistakeTitle")}
          description={t("mistakeDesc", {
            title: reporting.session.title,
            date: fmtDate(reporting.session.starts_at),
            status: statusText(reporting.status ?? "", t) || t("st_att_unmarked"),
          })}
          submitLabel={t("sendRequest")}
          fields={[
            {
              name: "status",
              label: t("mistakeShould"),
              kind: "select",
              options: ATTENDANCE_STATUSES.filter((s) => s !== reporting.status),
              optionLabels: Object.fromEntries(ATTENDANCE_STATUSES.map((s) => [s, statusText(s, t)])),
            },
            { name: "reason", label: t("reasonLabel"), kind: "textarea", required: true, hint: t("mistakeHint") },
          ]}
          onSubmit={(v) =>
            correct.mutateAsync({
              session_id: reporting.session.session_id,
              enrolment_id: block.enrolment.enrolment_id,
              requested_status: v["status"] as (typeof ATTENDANCE_STATUSES)[number],
              reason: v["reason"]!,
            })
          }
        />
      )}
    </Section>
  );
}

export function AttendanceTab() {
  const t = useT();
  const query = useMyAttendance();
  return (
    <div className="space-y-4">
      <QueryView query={query} isEmpty={(blocks) => blocks.length === 0} empty={t("attendanceBlocks")}>
        {(blocks) => blocks.map((block) => <AttendanceTable key={block.enrolment.enrolment_id} block={block} />)}
      </QueryView>
      <HowThisWorks title={t("howAttendanceWorks")}>
        <ul className="list-disc space-y-1 pl-5">
          {(["attendanceRule1", "attendanceRule2", "attendanceRule3", "attendanceRule4"] as const).map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
      </HowThisWorks>
    </div>
  );
}
