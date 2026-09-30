import { useQuery } from "@tanstack/react-query";
import { profileApi, type FinanceEntry } from "@/api/profile";
import { DataTable, Note, PageHead, QueryView, Section, StatusNote } from "@/components/lms/ui";
import { formatDate, formatIst, formatMoney } from "@/features/shared/ist";
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
          {summary.next_due_date && (
            <p className="text-sm">
              Next due: <strong>{formatMoney(summary.next_due_amount)}</strong> on <strong>{formatDate(summary.next_due_date)}</strong>
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
              { h: "Date", c: (r) => formatDate(r.date) },
            ]}
          />
          <p className="text-xs text-muted-foreground">
            As of {formatIst(summary.as_of)} · source: {entry.source}
          </p>
        </div>
      )}
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
          </>
        )}
      </QueryView>
      <Note>CRM remains authoritative for Admission and finance. The LMS never writes to CRM records. Payment actions are not available here.</Note>
    </div>
  );
}
