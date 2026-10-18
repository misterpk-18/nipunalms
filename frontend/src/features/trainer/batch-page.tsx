import { useState } from "react";
import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { trainerApi, trainerKeys } from "@/api/trainer";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { DataTable, Grid, PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { StateBadge } from "@/features/shared/delivery-ui";
import { fmtDate, fmtDateTime } from "@/features/shared/format";
import { CourseOutlineBlock } from "./course-outline-block";
import { FlagStudentDialog, type FlagTarget } from "./flag-student";
import { ReasonTags, pct } from "./risk";

function Figure({ label, value, to }: { label: string; value: string; to?: { batch: number } }) {
  const body = (
    <div className="rounded-lg border bg-muted/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
  return to ? (
    <Link to="/trainer/students" search={to} className="block hover:opacity-80">
      {body}
    </Link>
  ) : (
    body
  );
}

export function TrainerBatchPage() {
  const { id } = useParams({ from: "/trainer/batches/$id" });
  const batchId = Number(id);
  const query = useQuery({ queryKey: trainerKeys.batch(batchId), queryFn: () => trainerApi.batch(batchId), enabled: Number.isInteger(batchId) && batchId > 0 });
  const [flagging, setFlagging] = useState<FlagTarget | null>(null);

  return (
    <div className="mx-auto max-w-6xl">
      <QueryView query={query} skeleton="detail">
        {(page) => {
          const batch = page.batch;
          return (
            <>
              <Breadcrumbs items={[{ label: "Batches", to: "/trainer/batches" }, { label: batch.display_name ?? batch.batch_code }]} />
              <PageHead
                title={batch.display_name ?? batch.batch_code}
                description={
                  <>
                    <span className="font-mono">{batch.batch_code}</span> · {batch.course.title} · {batch.mode} · {fmtDate(batch.planned_start)} to{" "}
                    {fmtDate(batch.planned_end)}
                  </>
                }
                actions={<StateBadge label={batch.state_label} />}
              />
              <div className="space-y-4">
                <Section title="How the batch is going">
                  <Grid cols={4}>
                    <Figure label="Students" value={`${page.progress.students} of ${batch.capacity}`} to={{ batch: batch.batch_id }} />
                    <Figure label="Classes covered" value={pct(page.progress.delivery_pct)} />
                    <Figure label="Average attendance" value={pct(page.progress.attendance_pct)} />
                    <Figure label="Need attention" value={String(page.progress.at_risk)} to={{ batch: batch.batch_id }} />
                  </Grid>
                  <p className="mt-3 text-xs text-muted-foreground">
                    {`Course ${batch.course.title}`}
                    {batch.schedule_days.length > 0 &&
                      ` · ${batch.schedule_days.join(", ")} ${batch.start_time ?? ""}${batch.end_time ? `–${batch.end_time}` : ""}`}
                    {batch.location && ` · ${batch.location}`}
                  </p>
                </Section>

                <Section
                  title="Classes"
                  actions={
                    <Button asChild size="sm" variant="outline">
                      <Link to="/trainer/sessions">Open Sessions</Link>
                    </Button>
                  }
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <h3 className="mb-2 text-sm font-semibold">Coming up</h3>
                      {page.sessions.coming.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No class is scheduled. Your Branch Manager creates the classes.</p>
                      ) : (
                        <ul className="space-y-1.5 text-sm">
                          {page.sessions.coming.map((s) => (
                            <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2">
                              <span>
                                {s.title} <span className="text-muted-foreground">· {fmtDateTime(s.starts_at)}</span>
                              </span>
                              <Button asChild size="sm" variant="ghost">
                                <Link to="/trainer" search={{ session: s.session_id }}>
                                  Open class
                                </Link>
                              </Button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div>
                      <h3 className="mb-2 text-sm font-semibold">Recent</h3>
                      {page.sessions.recent.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No class has been held yet.</p>
                      ) : (
                        <ul className="space-y-1.5 text-sm">
                          {page.sessions.recent.map((s) => (
                            <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2">
                              <span>
                                {s.title} <span className="text-muted-foreground">· {fmtDate(s.starts_at)}</span>
                              </span>
                              <StateBadge label={s.state_label} />
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </Section>

                <CourseOutlineBlock courseId={batch.course.course_id} />

                <Section title="Students">
                  <DataTable
                    caption="Students in this batch"
                    rows={page.roster}
                    getKey={(r) => r.enrolment.enrolment_id}
                    empty="No student holds a seat in this batch yet."
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
                      { h: "Attendance", c: (r) => pct(r.attendance_pct) },
                      { h: "Needs attention", c: (r) => <ReasonTags reasons={r.reasons} /> },
                      {
                        h: "Support",
                        c: (r) =>
                          r.open_requests > 0 ? (
                            <Tag tone="warning">{`${r.open_requests} open`}</Tag>
                          ) : (
                            <span className="text-sm text-muted-foreground">None</span>
                          ),
                      },
                      {
                        h: "",
                        c: (r) => (
                          <Button size="sm" variant="ghost" onClick={() => setFlagging(r.student)} aria-label={`Flag ${r.student.full_name}`}>
                            Flag
                          </Button>
                        ),
                      },
                    ]}
                  />
                </Section>

                <Section
                  title="Assignments"
                  actions={
                    <Button asChild size="sm" variant="outline">
                      <Link to="/trainer/assignments">Open Assignments</Link>
                    </Button>
                  }
                >
                  <DataTable
                    caption="Assignments of this batch"
                    rows={page.assignments}
                    getKey={(a) => a.assignment_id}
                    empty="No assignment has been written for this batch yet."
                    emptyAction={
                      <Button asChild size="sm">
                        <Link to="/trainer/assignments">Write one</Link>
                      </Button>
                    }
                    cols={[
                      { h: "Assignment", c: (a) => <span className="font-medium">{a.title}</span> },
                      { h: "Due", c: (a) => fmtDate(a.due_at) },
                      { h: "State", c: (a) => <StatusBadge domain="assignment" code={a.status} /> },
                      { h: "Hand-ins", c: (a) => (a.counts ? `${a.counts.submitted} in · ${a.counts.awaiting_review} to grade` : "—") },
                    ]}
                  />
                </Section>

                <Section
                  title="Content"
                  actions={
                    <Button asChild size="sm" variant="outline">
                      <Link to="/trainer/content" search={{ batch: batch.batch_id }}>
                        Open Content
                      </Link>
                    </Button>
                  }
                >
                  <DataTable
                    caption="Content of this batch"
                    rows={page.content}
                    getKey={(c) => c.content_item_id}
                    empty="Nothing has been uploaded for this batch yet."
                    emptyAction={
                      <Button asChild size="sm">
                        <Link to="/trainer/content" search={{ batch: batch.batch_id }}>
                          Upload content
                        </Link>
                      </Button>
                    }
                    cols={[
                      { h: "Item", c: (c) => <span className="font-medium">{c.title}</span> },
                      { h: "Kind", c: (c) => c.content_type },
                      { h: "State", c: (c) => <StatusBadge domain="content" code={c.status} /> },
                    ]}
                  />
                </Section>
              </div>
              {flagging && <FlagStudentDialog key={flagging.student_id} open student={flagging} onOpenChange={(open) => !open && setFlagging(null)} />}
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
