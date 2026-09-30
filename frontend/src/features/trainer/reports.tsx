import { useTrainerReports, type TrainerReports as Reports } from "@/api/dashboards";
import { Grid, Note, PageHead, QueryView, Section, StatusNote } from "@/components/lms/ui";
import { Meter } from "@/features/shared/attendance-parts";
import { CardGap } from "@/features/shared/dashboard-parts";
import { fmtDateTime } from "@/features/shared/format";

function PerBatch({ reports, measure }: { reports: Reports; measure: "delivery" | "attendance" }) {
  const batches = reports.batches;
  if (batches.state !== "Ready") return <CardGap card={batches} />;
  return (
    <ul className="space-y-4">
      {batches.rows.map((row) => (
        <li key={row.batch.batch_id}>
          <Meter
            value={row[measure].percent}
            label={`${row.batch.batch_code} · ${row.students} student${row.students === 1 ? "" : "s"}${row.batch_state === "Running" ? "" : ` · ${row.batch_state}`}`}
          />
          {measure === "attendance" && row.attendance.state === "Partial Data" && (
            <div className="mt-2">
              <StatusNote state="Partial Data">
                {row.attendance.partial_data} student(s) have unmarked delivered classes, so the batch average is provisional.
              </StatusNote>
            </div>
          )}
          {measure === "delivery" && row.delivery.percent === null && (
            <p className="mt-1 text-xs text-muted-foreground">No class is planned yet, so delivery cannot be calculated.</p>
          )}
        </li>
      ))}
    </ul>
  );
}

function Turnaround({ data }: { data: Reports["review_turnaround"] }) {
  if (data.state === "Unavailable") return <StatusNote state="Error">{data.message}</StatusNote>;
  if (data.state === "Empty") return <StatusNote state="Empty">{data.message}</StatusNote>;
  return (
    <div className="space-y-2">
      <p className="text-3xl font-semibold tabular-nums">{data.average_hours === null ? "—" : `${data.average_hours} h`}</p>
      <p className="text-xs text-muted-foreground">
        Average time from submission to review across {data.measured} of {data.reviewed} reviewed submission(s).
      </p>
      {data.state === "Partial Data" && <StatusNote state="Partial Data">{data.message}</StatusNote>}
    </div>
  );
}

function Engagement({ data }: { data: Reports["engagement"] }) {
  if (data.state === "Stale") return <StatusNote state="Stale">{data.message} Shown as Stale rather than as zero.</StatusNote>;
  if (data.state === "Unavailable") return <StatusNote state="Error">{data.message}</StatusNote>;
  return (
    <StatusNote state="Saved">
      Latest learning activity across {data.students} student(s): {fmtDateTime(data.refreshed_at)}.
    </StatusNote>
  );
}

export function TrainerReports() {
  const query = useTrainerReports();
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead title="Reports" description="Assigned batches only · source: LMS reporting" />
      <QueryView query={query}>
        {(reports) => (
          <>
            <Grid cols={2}>
              <Section title="Curriculum delivered">
                <PerBatch reports={reports} measure="delivery" />
              </Section>
              <Section title="Attendance (trainer-confirmed)">
                <PerBatch reports={reports} measure="attendance" />
                <p className="mt-3 text-xs text-muted-foreground">Batch average of the attendance you confirmed. Approved recovery is reported separately.</p>
              </Section>
              <Section title="Review turnaround">
                <Turnaround data={reports.review_turnaround} />
              </Section>
              <Section title="Engagement">
                <Engagement data={reports.engagement} />
              </Section>
            </Grid>
            <Note>{reports.scope_note}</Note>
          </>
        )}
      </QueryView>
    </div>
  );
}
