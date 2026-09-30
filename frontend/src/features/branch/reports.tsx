import { useBranchSummary } from "@/api/attendance";
import { DataTable, Grid, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { percent } from "@/features/shared/format";
import { CertificateRegister } from "@/features/shared/certificate-register";

function Counts({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>;
  return (
    <ul className="flex flex-wrap gap-2">
      {entries.map(([label, n]) => (
        <li key={label}>
          <StatusBadge>{`${label}: ${n}`}</StatusBadge>
        </li>
      ))}
    </ul>
  );
}

export function BranchReports() {
  const summary = useBranchSummary({});
  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHead
        title="Branch certificates & reports"
        description="Certificate Register entries for the branch and attendance, progress and completion summaries."
      />
      <Section title="Certificate Register">
        <CertificateRegister />
      </Section>
      <QueryView query={summary}>
        {(data) => (
          <>
            <Section title="Attendance and progress by batch">
              <DataTable
                caption="Batch summaries"
                rows={data.batches}
                getKey={(b) => b.batch.batch_id}
                empty="No batch has allocated students yet."
                cols={[
                  { h: "Batch", c: (b) => `${b.batch.batch_code} (${b.batch.course_code})` },
                  { h: "Students", c: (b) => b.students },
                  { h: "Curriculum delivered", c: (b) => percent(b.avg_delivery) },
                  { h: "Attendance", c: (b) => percent(b.avg_attendance) },
                  { h: "Required learning", c: (b) => percent(b.avg_required_learning) },
                  {
                    h: "Alerts",
                    c: (b) => (b.attendance_alerts > 0 ? <StatusBadge tone="danger">{`${b.attendance_alerts} below threshold`}</StatusBadge> : "None"),
                  },
                  { h: "Partial data", c: (b) => (b.partial_data > 0 ? <StatusBadge tone="warning">{`${b.partial_data} student(s)`}</StatusBadge> : "None") },
                ]}
              />
              <p className="mt-2 text-xs text-muted-foreground">Each measure is averaged on its own; there is no combined score.</p>
            </Section>
            <Grid cols={2}>
              <Section title="Enrolments by status">
                <Counts counts={data.enrolments_by_status} />
              </Section>
              <Section title="Certificates by status">
                <Counts counts={data.certificates_by_status} />
              </Section>
            </Grid>
          </>
        )}
      </QueryView>
    </div>
  );
}
