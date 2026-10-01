import { useQuery } from "@tanstack/react-query";
import { profileApi, type FinanceEntry, type FinanceSchedule } from "@/api/profile";
import { DataTable, Note, PageHead, QueryView, Section, StatusNote } from "@/components/lms/ui";
import { fmtDateTime, fmtDate } from "@/features/shared/format";
import { formatMoney } from "@/lib/format";
import { useT } from "@/lib/i18n";

function Amount({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}

function AdmissionFinance({ entry }: { entry: FinanceEntry }) {
  const summary = entry.summary;
  return (
    <Section title={`${entry.admission.admission_code} · ${entry.course.title}`}>
      {summary === null ? (
        <StatusNote state="Pending Verification">The CRM has not sent a finance summary for this admission yet.</StatusNote>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Amount label="Fee" value={formatMoney(summary.fee_total)} />
            <Amount label="Verified receipts" value={formatMoney(summary.verified_paid)} />
            <Amount label="Dues" value={formatMoney(summary.balance)} />
          </div>
          {summary.installments_scope === "invoice" && summary.invoice_numbers[0] && (
            <p className="text-sm text-muted-foreground">
              Instalments are on invoice <span className="font-mono">{summary.invoice_numbers[0]}</span>
              {summary.invoice_course_count > 1 ? `, shared by ${summary.invoice_course_count} courses` : ""}: see Instalments below.
            </p>
          )}
          <DataTable
            caption={`Receipts for ${entry.admission.admission_code}`}
            rows={summary.receipts}
            getKey={(r) => r.receipt_number}
            empty="No verified receipts yet."
            cols={[
              { h: "Receipt", c: (r) => <span className="font-mono text-xs">{r.receipt_number}</span> },
              { h: "Amount", c: (r) => formatMoney(r.amount) },
              { h: "Date", c: (r) => fmtDate(r.date) },
            ]}
          />
          <p className="text-xs text-muted-foreground">
            As of {fmtDateTime(summary.as_of)} · source: {entry.source}
          </p>
        </div>
      )}
    </Section>
  );
}

/** One schedule, shown once: an invoice's instalments cover every course on that invoice. */
function ScheduleFinance({ schedule }: { schedule: FinanceSchedule }) {
  const courses = schedule.admissions.map((a) => a.course.title).join(" + ");
  const title = schedule.invoice_number ? `${schedule.invoice_number} · ${courses}` : `Instalments · ${courses}`;
  return (
    <Section title={title}>
      <div className="space-y-3">
        {schedule.next_due_date && (
          <p className="text-sm">
            Next due: <strong>{formatMoney(schedule.next_due_amount)}</strong> on <strong>{fmtDate(schedule.next_due_date)}</strong>
            {Number(schedule.overdue_amount) > 0 && (
              <>
                {" "}
                · Overdue: <strong>{formatMoney(schedule.overdue_amount)}</strong>
              </>
            )}
          </p>
        )}
        <DataTable
          caption={`Instalments for ${title}`}
          rows={schedule.installments}
          getKey={(i) => i.installment_no}
          empty="No instalment schedule from the CRM."
          cols={[
            { h: "#", c: (i) => i.installment_no },
            { h: "Due date", c: (i) => fmtDate(i.due_date) },
            { h: "Amount", c: (i) => formatMoney(i.amount) },
            { h: "Covered", c: (i) => formatMoney(i.covered) },
            { h: "Balance", c: (i) => formatMoney(i.balance) },
            { h: "Status", c: (i) => i.due_position ?? "—" },
          ]}
        />
        <p className="text-xs text-muted-foreground">As of {fmtDateTime(schedule.as_of)}</p>
      </div>
    </Section>
  );
}

export function Finance() {
  const t = useT();
  const query = useQuery({ queryKey: ["finance", "me"], queryFn: profileApi.finance });
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead title={t("finance")} description="Read-only · permitted summary · CRM (authoritative)" />
      <QueryView query={query} isEmpty={(d) => d.admissions.length === 0} empty="No admissions are linked to your account.">
        {(data) => (
          <>
            <StatusNote state="Pending Verification">{data.note}</StatusNote>
            {data.admissions.map((entry) => (
              <AdmissionFinance key={entry.admission.admission_id} entry={entry} />
            ))}
            {data.schedules.length > 0 && <h2 className="pt-2 text-lg font-semibold">Instalments</h2>}
            {data.schedules.map((schedule) => (
              <ScheduleFinance key={schedule.schedule_key} schedule={schedule} />
            ))}
          </>
        )}
      </QueryView>
      <Note>CRM remains authoritative for Admission and finance. The LMS never writes to CRM records. Payment actions are not available here.</Note>
    </div>
  );
}
