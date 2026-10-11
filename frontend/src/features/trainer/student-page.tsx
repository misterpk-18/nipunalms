import { useState } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { trainerApi, trainerKeys, type StudentPage } from "@/api/trainer";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { EmptyState } from "@/components/lms/empty-state";
import { DataTable, Grid, PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { fmtDate } from "@/features/shared/format";
import { FlagStudentDialog } from "./flag-student";
import { ReasonList, pct } from "./risk";

type Seat = StudentPage["enrolments"][number];

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function WorkState({ row }: { row: Seat["assignments"][number] }) {
  if (row.state === "Not submitted") return <Tag tone={row.overdue ? "danger" : "neutral"}>{row.overdue ? "Not handed in, overdue" : "Not handed in yet"}</Tag>;
  if (row.state === "Reviewed") return <Tag tone="success">Reviewed</Tag>;
  if (row.state === "Resubmission Requested") return <Tag tone="warning">Asked to resubmit</Tag>;
  return <Tag tone="info">{row.state === "Under Review" ? "Review started" : "Waiting for you"}</Tag>;
}

function SeatSections({ seat }: { seat: Seat }) {
  return (
    <div className="space-y-4">
      <Section title={`${seat.enrolment.course.title} · ${seat.batch.batch_code}`}>
        <Grid cols={4}>
          <Figure label="Attendance" value={pct(seat.attendance_pct)} />
          <Figure label="Classes covered" value={pct(seat.delivery_pct)} />
          <Figure label="Required work" value={pct(seat.required_pct)} />
          <Figure label="Classes not marked" value={String(seat.unmarked)} />
        </Grid>
        <p className="mt-3 text-sm">
          <Link to="/trainer/batches/$id" params={{ id: String(seat.batch.batch_id) }} className="text-primary underline-offset-2 hover:underline">
            Open batch {seat.batch.batch_code}
          </Link>
        </p>
      </Section>
      <Section title="Attendance">
        <DataTable
          caption="Recent classes"
          rows={seat.attendance}
          getKey={(a) => a.session_id}
          empty="No class has been held for this student yet."
          cols={[
            { h: "Class", c: (a) => a.title },
            { h: "Date", c: (a) => fmtDate(a.starts_at) },
            { h: "Marked as", c: (a) => (a.status ? <StatusBadge domain="attendance" code={a.status} /> : <Tag tone="warning">Not marked</Tag>) },
            {
              h: "",
              c: (a) =>
                a.status === null ? (
                  <Button asChild size="sm" variant="outline">
                    <Link to="/trainer/attendance" search={{ session: a.session_id }}>
                      Mark attendance
                    </Link>
                  </Button>
                ) : null,
            },
          ]}
        />
      </Section>
      <Section title="Work">
        <DataTable
          caption="Assignments"
          rows={seat.assignments}
          getKey={(a) => a.assignment.assignment_id}
          empty="No assignment has been released to this batch yet."
          cols={[
            { h: "Assignment", c: (a) => <span className="font-medium">{a.assignment.title}</span> },
            { h: "Due", c: (a) => fmtDate(a.due_at) },
            { h: "State", c: (a) => <WorkState row={a} /> },
            { h: "Marks", c: (a) => (a.marks !== null ? `${a.marks} / ${a.max_marks}` : "—") },
            {
              h: "",
              c: (a) =>
                a.to_grade && a.submission_id !== null ? (
                  <Button asChild size="sm">
                    <Link to="/trainer/to-grade/$kind/$id" params={{ kind: "submission", id: String(a.submission_id) }}>
                      Grade
                    </Link>
                  </Button>
                ) : null,
            },
          ]}
        />
      </Section>
      <Section title="Results">
        <DataTable
          caption="Results"
          rows={seat.results}
          getKey={(r, i) => `${r.item.title}-${i}`}
          empty="No marks have been recorded for this student yet."
          cols={[
            { h: "Work", c: (r) => r.item.title },
            { h: "Kind", c: (r) => r.item.type },
            { h: "Marks", c: (r) => `${r.marks} / ${r.max_marks}` },
            { h: "State", c: (r) => <StatusBadge domain="result" code={r.status} /> },
          ]}
        />
      </Section>
    </div>
  );
}

export function TrainerStudentPage() {
  const { id } = useParams({ from: "/trainer/students/$id" });
  const studentId = Number(id);
  const query = useQuery({
    queryKey: trainerKeys.student(studentId),
    queryFn: () => trainerApi.student(studentId),
    enabled: Number.isInteger(studentId) && studentId > 0,
  });
  const [flagging, setFlagging] = useState(false);

  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query} skeleton="detail">
        {(page) => {
          const reasons = page.enrolments.flatMap((e) => e.reasons);
          return (
            <>
              <Breadcrumbs items={[{ label: "Students", to: "/trainer/students" }, { label: page.student.full_name }]} />
              <PageHead
                title={page.student.full_name}
                description={<span className="font-mono">{page.student.student_code}</span>}
                actions={<Button onClick={() => setFlagging(true)}>Flag this student</Button>}
              />
              <div className="space-y-4">
                {reasons.length > 0 && (
                  <Section title="Needs your attention">
                    <ReasonList reasons={reasons} />
                  </Section>
                )}
                {page.enrolments.map((seat) => (
                  <SeatSections key={seat.enrolment.enrolment_id} seat={seat} />
                ))}
                <Section title="Support requests">
                  {page.flags.length === 0 ? (
                    <EmptyState reason="No support request has been raised about this student by you or to you." />
                  ) : (
                    <ul className="divide-y">
                      {page.flags.map((f) => (
                        <li key={f.support_request_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                          <div className="min-w-0">
                            <span className="font-mono text-xs">{f.request_code}</span> · {f.category} · {f.subject}
                            <div className="text-xs text-muted-foreground">Owner: {f.owner.label}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            <StatusBadge domain="support" code={f.status} />
                            <Button asChild size="sm" variant="outline">
                              <Link to="/trainer/support">Open Support</Link>
                            </Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>
              </div>
              {flagging && <FlagStudentDialog open student={page.student} onOpenChange={(open) => !open && setFlagging(false)} />}
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
