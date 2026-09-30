import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi } from "@/api/delivery";
import { Input } from "@/components/ui/input";
import { DataTable, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { fmtRange, mono, useCanManage } from "@/features/shared/delivery-ui";
import { RequestsPanel, RosterDialog, SessionsTable } from "@/features/shared/sessions";

/** Branch Manager: batches, schedule exceptions, trainers and students of the branch. */
export function BranchOperations() {
  const manager = useCanManage();
  const [q, setQ] = useState("");
  const batches = useQuery({ queryKey: ["delivery", "batches", "branch"], queryFn: () => deliveryApi.batches({}) });
  const upcoming = useQuery({ queryKey: ["delivery", "sessions", "branch-upcoming"], queryFn: () => deliveryApi.sessions({ upcoming: true }) });
  const cancelled = useQuery({ queryKey: ["delivery", "sessions", "branch-cancelled"], queryFn: () => deliveryApi.sessions({ state: "Cancelled" }) });
  const people = useQuery({ queryKey: ["delivery", "enrolments", "branch", q], queryFn: () => deliveryApi.enrolments({ q: q || undefined }) });

  return (
    <>
      <PageHead title="Batches, schedule & people" description="Batches, schedule exceptions, trainers and students at your branch." />
      <div className="space-y-6">
        <Section title="Batches">
          <QueryView query={batches}>
            {(page) => (
              <DataTable
                caption="Batches"
                rows={page.data}
                getKey={(b) => b.batch_id}
                cols={[
                  { h: "Batch", c: (b) => mono(b.batch_code) },
                  { h: "Course", c: (b) => b.course.title },
                  { h: "Trainer", c: (b) => b.trainers.map((t) => t.full_name).join(", ") || "Unassigned" },
                  { h: "Seats", c: (b) => <RosterDialog batch={b} /> },
                  { h: "State", c: (b) => <StatusBadge>{b.state}</StatusBadge> },
                  {
                    h: "Readiness",
                    c: (b) => (
                      <>
                        <StatusBadge>{b.readiness}</StatusBadge>
                        {b.readiness_reason && (
                          <div className="mt-1 text-xs text-muted-foreground">
                            {b.readiness_reason}
                            {b.recovery_owner ? ` · ${b.recovery_owner}` : ""}
                          </div>
                        )}
                      </>
                    ),
                  },
                ]}
              />
            )}
          </QueryView>
        </Section>

        <Section title="Schedule exceptions">
          <h3 className="mb-2 text-sm font-semibold">Reschedule requests waiting for a decision</h3>
          <RequestsPanel manager={manager} />
          <h3 className="mb-2 mt-4 text-sm font-semibold">Upcoming classes that were moved or have no working Meet link</h3>
          <QueryView query={upcoming}>
            {(page) => (
              <SessionsTable
                caption="Upcoming exceptions"
                rows={page.data.filter((s) => s.state === "Rescheduled" || (s.mode !== "Classroom" && s.meet_status !== "Linked"))}
                actions={manager ? { manager: true, trainer: false } : null}
              />
            )}
          </QueryView>
          <h3 className="mb-2 mt-4 text-sm font-semibold">Cancelled classes</h3>
          <QueryView query={cancelled}>
            {(page) => (
              <DataTable
                caption="Cancelled classes"
                rows={page.data}
                getKey={(s) => s.session_id}
                empty="No cancelled classes."
                cols={[
                  { h: "Was scheduled", c: (s) => fmtRange(s.starts_at, s.ends_at) },
                  { h: "Session", c: (s) => s.title },
                  { h: "Batch", c: (s) => mono(s.batch.batch_code) },
                  { h: "Trainer", c: (s) => s.trainer.full_name },
                ]}
              />
            )}
          </QueryView>
        </Section>

        <Section title="Trainers">
          <QueryView query={batches}>
            {(page) => {
              const rows = page.data.flatMap((b) => b.trainers.map((t) => ({ ...t, batch: b })));
              return (
                <DataTable
                  caption="Trainers"
                  rows={rows}
                  getKey={(r) => `${r.batch.batch_id}-${r.user_id}`}
                  empty="No trainer is assigned to a batch."
                  cols={[
                    { h: "Trainer", c: (r) => r.full_name },
                    { h: "Role", c: (r) => r.role },
                    { h: "Batch", c: (r) => mono(r.batch.batch_code) },
                    { h: "Course", c: (r) => r.batch.course.title },
                  ]}
                />
              );
            }}
          </QueryView>
        </Section>

        <Section title="Students">
          <div className="mb-3 max-w-sm">
            <Input aria-label="Search students" placeholder="Search by name, Student ID or enrolment code" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <QueryView query={people}>
            {(page) => (
              <DataTable
                caption="Students"
                rows={page.data}
                getKey={(r) => r.enrolment_id}
                empty="No students match."
                cols={[
                  { h: "Student", c: (r) => `${r.student.full_name} (${r.student.student_code})` },
                  { h: "Course", c: (r) => `${r.course.course_code} · ${r.kind}` },
                  { h: "Batch", c: (r) => (r.batch ? mono(r.batch.batch_code) : "Not allocated") },
                  { h: "Status", c: (r) => <StatusBadge>{r.status}</StatusBadge> },
                ]}
              />
            )}
          </QueryView>
        </Section>
      </div>
    </>
  );
}
