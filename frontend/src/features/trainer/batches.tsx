import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { trainerApi, trainerKeys } from "@/api/trainer";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, PageHead, QueryView, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { StateBadge } from "@/features/shared/delivery-ui";
import { fmtDate, fmtDateTime } from "@/features/shared/format";
import { pct } from "./risk";

export function TrainerBatches() {
  const query = useQuery({ queryKey: trainerKeys.batches, queryFn: trainerApi.batches });
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title="Batches" description="The batches you teach. Open one for its classes, students, content, assignments and progress." />
      <QueryView
        query={query}
        isEmpty={(rows) => rows.length === 0}
        empty="No batch is assigned to you yet. Your Branch Manager adds you to a batch when it is set up."
      >
        {(rows) => (
          <DataTable
            caption="My batches"
            rows={rows}
            getKey={(r) => r.batch.batch_id}
            cols={[
              {
                h: "Batch",
                c: (r) => (
                  <>
                    <Link
                      to="/trainer/batches/$id"
                      params={{ id: String(r.batch.batch_id) }}
                      className="font-medium text-primary underline-offset-2 hover:underline"
                    >
                      {r.batch.display_name ?? r.batch.batch_code}
                    </Link>
                    <div className="font-mono text-xs text-muted-foreground">{r.batch.batch_code}</div>
                  </>
                ),
              },
              { h: "Course", c: (r) => r.batch.course.title },
              { h: "Dates", c: (r) => `${fmtDate(r.batch.planned_start)} to ${fmtDate(r.batch.planned_end)}` },
              { h: "State", c: (r) => <StateBadge label={r.batch.state_label} /> },
              { h: "Students", c: (r) => `${r.students} of ${r.batch.capacity}` },
              { h: "Next class", c: (r) => (r.next_class ? `${r.next_class.title}, ${fmtDateTime(r.next_class.starts_at)}` : "None scheduled") },
              { h: "Attendance", c: (r) => pct(r.attendance_pct) },
              {
                h: "Needs attention",
                c: (r) =>
                  r.at_risk > 0 ? (
                    <Link to="/trainer/students" search={{ batch: r.batch.batch_id }}>
                      <Tag tone="warning">{`${r.at_risk} student${r.at_risk === 1 ? "" : "s"}`}</Tag>
                    </Link>
                  ) : (
                    <span className="text-sm text-muted-foreground">No one</span>
                  ),
              },
              {
                h: "",
                c: (r) => (
                  <Button asChild size="sm" variant="outline">
                    <Link to="/trainer/batches/$id" params={{ id: String(r.batch.batch_id) }}>
                      Open
                    </Link>
                  </Button>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <HowThisWorks>
          <p>Your Branch Manager sets up batches, timetables and students. Here you see how each batch is going and where to act.</p>
        </HowThisWorks>
      </div>
    </div>
  );
}
