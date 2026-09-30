import { useAcademicReports, type AcademicReportBlock } from "@/api/dashboards";
import { useBranchSummary } from "@/api/attendance";
import { DataTable, Grid, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Meter } from "@/features/shared/attendance-parts";
import { percent } from "@/features/shared/format";

function Delivered({ block }: { block: AcademicReportBlock["curriculum_delivered"] }) {
  if (block.state === "Unavailable" || block.state === "Empty")
    return <StatusNote state={block.state === "Empty" ? "Empty" : "Error"}>{block.message}</StatusNote>;
  return (
    <div className="space-y-2">
      <Meter value={block.percent ?? null} label={`All running batches (${block.batches})`} />
      {block.state === "Partial Data" && <StatusNote state="Partial Data">{block.message}</StatusNote>}
    </div>
  );
}

function Attendance({ block }: { block: AcademicReportBlock["attendance"] }) {
  if (block.state === "Unavailable") return <StatusNote state="Error">{block.message}</StatusNote>;
  const recovery = block.recovery;
  return (
    <div className="space-y-2">
      {block.state === "Empty" ? (
        <StatusNote state="Empty">{block.message}</StatusNote>
      ) : (
        <Meter value={block.percent ?? null} label="Branch average (trainer-confirmed)" />
      )}
      {block.state === "Partial Data" && (
        <StatusNote state="Partial Data">{block.partial_data_students} student(s) have unmarked delivered classes, so the average is provisional.</StatusNote>
      )}
      {recovery && (
        <p className="text-xs text-muted-foreground">
          Approved recovery: {recovery.approved_or_completed} ({recovery.completed} completed) · Requested {recovery.requested} · Rejected {recovery.rejected}
          {block.alerts ? ` · ${block.alerts} student(s) below the attendance alert` : ""}. Recovery is reported separately from attendance.
        </p>
      )}
    </div>
  );
}

function Completion({ block }: { block: AcademicReportBlock["completion_reviews"] }) {
  if (block.state === "Unavailable") return <StatusNote state="Error">{block.message}</StatusNote>;
  if (block.state === "Empty") return <StatusNote state="Empty">{block.message}</StatusNote>;
  return (
    <div className="space-y-2">
      <p className="text-3xl font-semibold tabular-nums">{block.closed}</p>
      <p className="text-xs text-muted-foreground">Completion reviews closed · {block.open} still open</p>
      {block.state === "Partial Data" && <StatusNote state="Partial Data">{block.message}</StatusNote>}
    </div>
  );
}

function LeadTime({ block }: { block: AcademicReportBlock["certificate_lead_time"] }) {
  if (block.state === "Unavailable") return <StatusNote state="Error">{block.message}</StatusNote>;
  if (block.state !== "Calculated") return <StatusNote state="Integration Unavailable">Not Configured. {block.message}</StatusNote>;
  return (
    <div className="space-y-1">
      <p className="text-3xl font-semibold tabular-nums">{block.average_days} days</p>
      <p className="text-xs text-muted-foreground">Average from completion decision to issue date across {block.issued} issued certificate(s).</p>
    </div>
  );
}

function BatchTable() {
  const summary = useBranchSummary({});
  return (
    <Section title="By batch">
      <QueryView query={summary}>
        {(data) => (
          <>
            <DataTable
              caption="Batch summaries"
              rows={data.batches}
              getKey={(b) => b.batch.batch_id}
              empty="No batch has allocated students yet."
              cols={[
                { h: "Batch", c: (b) => `${b.batch.batch_code} (${b.batch.course_code})` },
                { h: "State", c: (b) => <StatusBadge>{b.state}</StatusBadge> },
                { h: "Students", c: (b) => b.students },
                { h: "Curriculum delivered", c: (b) => percent(b.avg_delivery) },
                { h: "Attendance", c: (b) => percent(b.avg_attendance) },
                { h: "Partial data", c: (b) => (b.partial_data > 0 ? <StatusBadge tone="warning">{`${b.partial_data} student(s)`}</StatusBadge> : "None") },
              ]}
            />
            <p className="mt-2 text-xs text-muted-foreground">Each measure is averaged on its own; there is no combined score.</p>
          </>
        )}
      </QueryView>
    </Section>
  );
}

export function AcademicReports() {
  const query = useAcademicReports();
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead title="Academic Reports" description="Branch figures · source: LMS reporting" />
      <QueryView query={query} isEmpty={(data) => data.branches.length === 0} empty="No branch to report on.">
        {(data) => (
          <>
            {data.branches.map((block) => (
              <div key={block.branch.branch_id} className="space-y-3" data-testid={`report-${block.branch.branch_code}`}>
                {data.branches.length > 1 && <h2 className="text-lg font-semibold">{block.branch.branch_name}</h2>}
                <Grid cols={2}>
                  <Section title="Curriculum delivered (branch)">
                    <Delivered block={block.curriculum_delivered} />
                  </Section>
                  <Section title="Attendance / approved recovery">
                    <Attendance block={block.attendance} />
                  </Section>
                  <Section title="Completion reviews closed">
                    <Completion block={block.completion_reviews} />
                  </Section>
                  <Section title="Certificate issue lead time">
                    <LeadTime block={block.certificate_lead_time} />
                  </Section>
                </Grid>
              </div>
            ))}
            <BatchTable />
          </>
        )}
      </QueryView>
    </div>
  );
}
