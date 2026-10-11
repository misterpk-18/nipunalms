import { Link } from "@tanstack/react-router";
import { useTrainerReports, type TrainerReports as Reports } from "@/api/dashboards";
import { useAtRisk } from "@/api/trainer";
import { EmptyState } from "@/components/lms/empty-state";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, Grid, PageHead, QueryView, Section, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { ReasonTags, pct } from "./risk";

function Figure({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border bg-muted/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {note && <p className="mt-0.5 text-xs text-muted-foreground">{note}</p>}
    </div>
  );
}

/** The average of the batch figures that exist (a batch with nothing to calculate is left out, never counted as zero). */
function average(values: (number | null | undefined)[]): number | null {
  const known = values.filter((v): v is number => typeof v === "number");
  return known.length === 0 ? null : known.reduce((a, b) => a + b, 0) / known.length;
}

function Summary({ reports }: { reports: Reports }) {
  const rows = reports.batches.state === "Ready" ? reports.batches.rows : [];
  const attendance = average(rows.map((r) => r.attendance.percent));
  const delivery = average(rows.map((r) => r.delivery.percent));
  const provisional = rows.reduce((n, r) => n + (r.attendance.state === "Partial Data" ? r.attendance.partial_data : 0), 0);
  const turnaround = reports.review_turnaround;
  return (
    <Section title="Summary">
      <Grid cols={4}>
        <Figure
          label="Average attendance"
          value={pct(attendance)}
          note={provisional > 0 ? `${provisional} student(s) have unmarked classes, so this is provisional.` : undefined}
        />
        <Figure
          label="Classes covered"
          value={pct(delivery)}
          note={rows.some((r) => r.delivery.percent === null) ? "A batch with no class planned is left out." : undefined}
        />
        <Figure
          label="Time to review"
          value={turnaround.state === "Unavailable" || turnaround.average_hours == null ? "Not yet" : `${turnaround.average_hours} h`}
          note={turnaround.measured ? `Average over ${turnaround.measured} reviewed hand-ins.` : "Nothing has been reviewed yet."}
        />
        <Figure
          label="Student activity"
          value={reports.engagement.state === "Fresh" ? "Recent" : reports.engagement.state === "Stale" ? "Quiet" : "Not available"}
          note={reports.engagement.state === "Stale" ? (reports.engagement.message ?? undefined) : undefined}
        />
      </Grid>
      {turnaround.state === "Partial Data" && turnaround.message && (
        <div className="mt-3">
          <StatusNote tone="warning">{turnaround.message}</StatusNote>
        </div>
      )}
    </Section>
  );
}

export function TrainerReports() {
  const risk = useAtRisk();
  const reports = useTrainerReports();
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead title="Reports" description="Which students need you, and how your batches are doing." />
      <QueryView query={risk} skeleton="cards">
        {(data) =>
          data.batches.length === 0 ? (
            <EmptyState reason="You are not assigned to a batch yet, so there is nothing to report." />
          ) : (
            <>
              <section aria-label="Students who need you" className="space-y-3">
                <h2 className="text-lg font-semibold">
                  Students who need you
                  <span className="ml-2 text-sm font-normal text-muted-foreground">
                    {data.totals.at_risk} of {data.totals.students}
                  </span>
                </h2>
                {data.batches.map((b) => (
                  <Section
                    key={b.batch.batch_id}
                    title={b.batch.batch_code}
                    actions={
                      <div className="flex items-center gap-2">
                        <Tag tone={b.at_risk > 0 ? "warning" : "success"}>
                          {b.at_risk > 0 ? `${b.at_risk} of ${b.students} need attention` : "No one needs attention"}
                        </Tag>
                        <Button asChild size="sm" variant="ghost">
                          <Link to="/trainer/batches/$id" params={{ id: String(b.batch.batch_id) }}>
                            Open batch
                          </Link>
                        </Button>
                      </div>
                    }
                  >
                    {b.rows.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        {b.students === 0 ? "No student holds a seat in this batch yet." : "Attendance, work and reviews are on track for every student."}
                      </p>
                    ) : (
                      <DataTable
                        caption={`Students at risk in ${b.batch.batch_code}`}
                        rows={b.rows}
                        getKey={(r) => r.enrolment_id}
                        cols={[
                          {
                            h: "Student",
                            c: (r) => (
                              <Link
                                to="/trainer/students/$id"
                                params={{ id: String(r.student.student_id) }}
                                className="font-medium text-primary underline-offset-2 hover:underline"
                              >
                                {r.student.full_name}
                              </Link>
                            ),
                          },
                          { h: "Why", c: (r) => <ReasonTags reasons={r.reasons} /> },
                          {
                            h: "Where to act",
                            c: (r) => (
                              <div className="flex flex-wrap gap-2">
                                {[...new Map(r.reasons.map((reason) => [reason.to + reason.action, reason])).values()].map((reason) => (
                                  <Button key={reason.to + reason.action} asChild size="sm" variant="outline">
                                    <Link to={reason.to}>{reason.action}</Link>
                                  </Button>
                                ))}
                              </div>
                            ),
                          },
                        ]}
                      />
                    )}
                  </Section>
                ))}
              </section>
            </>
          )
        }
      </QueryView>
      <QueryView query={reports} skeleton="cards">
        {(data) => (
          <>
            <Summary reports={data} />
            <HowThisWorks>
              <p>{data.scope_note}</p>
              <p className="mt-2">
                A student needs attention when attendance is below the alert level, required work is missing or late, delivered classes are not marked, or your
                review of their work is overdue. Averages are taken across your batches and leave out anything that cannot be calculated yet.
              </p>
            </HowThisWorks>
          </>
        )}
      </QueryView>
    </div>
  );
}
