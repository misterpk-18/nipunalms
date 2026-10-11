/** The Students tab: students below the attendance alert first, search and batch filter, and a panel with the four measures of one student. */
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { attendanceApi, type ProgressBlock, type ProgressRow } from "@/api/attendance";
import { deliveryApi } from "@/api/delivery";
import { EmptyState } from "@/components/lms/empty-state";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, LoadingSkeleton, QueryView, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { AttendanceCell, Meter } from "@/features/shared/attendance-parts";
import { fmtDate, fmtDateTime, percent } from "@/features/shared/format";
import { Pager } from "./attendance-pager";

const PER_PAGE = 25;
const batchName = (b: { display_name?: string | null; batch_code: string }) => b.display_name ?? b.batch_code;

function Engagement({ level }: { level: ProgressRow["engagement"]["level"] }) {
  const tone = level === "High" ? "success" : level === "Medium" ? "info" : level === "Low" ? "warning" : "neutral";
  return <Tag tone={tone}>{level === "Not started" ? "No activity yet" : level}</Tag>;
}

export function StudentsTab({
  branchId,
  params,
  setParams,
}: {
  branchId: number | null;
  params: Record<string, string | undefined>;
  setParams: (patch: Record<string, string | number | undefined>) => void;
}) {
  const atRiskOnly = params["risk"] !== "0";
  const [q, setQ] = useState("");
  const [batch, setBatch] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<ProgressRow | null>(null);
  const search = q.trim();
  const batches = useQuery({ queryKey: ["delivery", "batches", "branch-filter", branchId], queryFn: () => deliveryApi.batches({ branch_id: branchId }) });
  const query = useQuery({
    queryKey: ["progress", "students", "branch", { branchId, atRiskOnly, search, batch, page }],
    queryFn: () =>
      attendanceApi.progress({
        sort: "risk",
        page,
        per_page: PER_PAGE,
        q: search || undefined,
        batch_id: batch ? Number(batch) : undefined,
        branch_id: branchId,
        alert: atRiskOnly ? true : undefined,
      }),
    placeholderData: keepPreviousData,
  });
  const reset = () => setPage(1);
  const filtered = Boolean(search || batch);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Input
          className="w-full sm:w-64"
          aria-label="Search students"
          placeholder="Search by name or admission number"
          value={q}
          onChange={(e) => (setQ(e.target.value), reset())}
        />
        <div className="w-full sm:w-56">
          <NativeSelect
            aria-label="Batch"
            placeholder="All batches"
            value={batch}
            onChange={(e) => (setBatch(e.target.value), reset())}
            options={(batches.data?.data ?? []).map((b) => ({ value: b.batch_id, label: batchName(b) }))}
          />
        </div>
        <Button variant="outline" aria-pressed={!atRiskOnly} onClick={() => (setParams({ risk: atRiskOnly ? "0" : undefined }), reset())}>
          {atRiskOnly ? "Show all students" : "Show only students at risk"}
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        {atRiskOnly
          ? "Showing students whose attendance is below the alert, the lowest first."
          : "Showing every student. Those below the attendance alert come first."}
      </p>
      <QueryView
        query={query}
        isEmpty={(result) => result.data.length === 0}
        empty={
          filtered
            ? "No student matches that search or batch."
            : atRiskOnly
              ? "No student is below the attendance alert. Everyone is on track."
              : "No student has started studying yet. Students appear here once they are in a batch."
        }
        emptyAction={
          atRiskOnly && !filtered ? (
            <Button size="sm" variant="outline" onClick={() => setParams({ risk: "0" })}>
              Show all students
            </Button>
          ) : filtered ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setQ("");
                setBatch("");
              }}
            >
              Clear the search
            </Button>
          ) : undefined
        }
      >
        {(result) => (
          <div className="space-y-3">
            <DataTable
              caption="Students"
              rows={result.data}
              getKey={(r) => r.enrolment.enrolment_id}
              cols={[
                {
                  h: "Student",
                  c: (r) => (
                    <button
                      type="button"
                      className="text-left font-medium text-primary underline-offset-2 hover:underline"
                      aria-label={`Open ${r.student.full_name}`}
                      onClick={() => setOpen(r)}
                    >
                      {r.student.full_name}
                      <span className="block text-xs font-normal text-muted-foreground">
                        {r.student.student_code} · {r.enrolment.course.course_code}
                      </span>
                    </button>
                  ),
                },
                { h: "Batch", c: (r) => (r.batch ? r.batch.batch_code : "No batch yet") },
                { h: "Attendance", c: (r) => <AttendanceCell measures={r.attendance} /> },
                { h: "Curriculum delivered", c: (r) => percent(r.delivery.percent) },
                { h: "Required learning", c: (r) => percent(r.required_learning.percent) },
                { h: "Engagement", c: (r) => <Engagement level={r.engagement.level} /> },
              ]}
            />
            <Pager meta={result.meta} onPage={setPage} noun="students" />
          </div>
        )}
      </QueryView>
      <StudentPanel row={open} onClose={() => setOpen(null)} />
    </div>
  );
}

function StudentPanel({ row, onClose }: { row: ProgressRow | null; onClose: () => void }) {
  const id = row?.enrolment.enrolment_id;
  const query = useQuery({ queryKey: ["progress", "enrolment", id], queryFn: () => attendanceApi.enrolmentProgress(id!), enabled: id !== undefined });
  return (
    <Sheet open={row !== null} onOpenChange={(next) => !next && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {row && (
          <>
            <SheetHeader>
              <SheetTitle>{row.student.full_name}</SheetTitle>
              <SheetDescription>
                {row.student.student_code} · {row.enrolment.course.title}
                {row.batch ? ` · ${row.batch.batch_code}` : ""}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-4 px-4 pb-6">
              <p className="text-sm text-muted-foreground">These are four separate measures. They are never added into one score, so read each on its own.</p>
              {query.isPending && <LoadingSkeleton kind="detail" />}
              {query.isError && <StatusNote tone="danger">Could not load this student's measures. Close the panel and try again.</StatusNote>}
              {query.data && <Measures block={query.data} />}
              <div className="flex flex-wrap gap-2 border-t pt-3">
                {row.batch && (
                  <Button asChild size="sm" variant="outline">
                    <Link to="/branch/batches/$id" params={{ id: String(row.batch.batch_id) }}>
                      Open the batch
                    </Link>
                  </Button>
                )}
                <Button asChild size="sm" variant="outline">
                  <Link to="/branch/support" search={{ student: row.student.student_id } as never}>
                    Student support
                  </Link>
                </Button>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Measures({ block }: { block: ProgressBlock }) {
  const { delivery, attendance: a, required_learning: learning, engagement: e } = block;
  return (
    <div className="space-y-4">
      <section aria-label="Curriculum delivered" className="space-y-1">
        <h3 className="text-sm font-semibold">Curriculum delivered</h3>
        <Meter value={delivery.percent} label={`${delivery.delivered_sessions} of ${delivery.planned_sessions} planned classes taught`} />
        <p className="text-xs text-muted-foreground">How much of the course the batch has been taught so far. It does not depend on this student.</p>
      </section>
      <section aria-label="Attendance" className="space-y-1">
        <h3 className="text-sm font-semibold">Attendance, with recovery</h3>
        {a.state === "Not started" ? (
          <EmptyState reason="Attendance starts counting from the student's first regular class." />
        ) : (
          <>
            <Meter value={a.percent} label={`${a.present + a.late} attended of ${a.marked} marked classes`} />
            <p className="text-xs text-muted-foreground">
              Present {a.present} · Late {a.late} · Absent {a.absent} · Excused {a.excused}
              {a.recovered > 0 ? ` · ${a.recovered} made up through approved recovery, counted separately` : ""}
            </p>
            {a.alert && (
              <StatusNote tone="danger">
                Attendance is below the alert of {a.alert_threshold}%. Look at the Recovery requests tab, or speak to the student.
              </StatusNote>
            )}
            {a.state === "Partial Data" && (
              <StatusNote tone="warning">{a.unmarked} delivered class(es) are not marked yet, so this figure may change.</StatusNote>
            )}
          </>
        )}
      </section>
      <section aria-label="Required learning" className="space-y-1">
        <h3 className="text-sm font-semibold">Required learning</h3>
        <Meter value={learning.percent} label={`${learning.covered_topics} of ${learning.required_topics} required topics covered`} />
        <p className="text-xs text-muted-foreground">Required topics the student has covered by attending or making up the class.</p>
      </section>
      <section aria-label="Engagement" className="space-y-1">
        <h3 className="text-sm font-semibold">Engagement</h3>
        <p className="text-sm">
          <Engagement level={e.level} /> {e.events_in_window} visit{e.events_in_window === 1 ? "" : "s"} to the LMS in the last {e.window_days} days
        </p>
        <p className="text-xs text-muted-foreground">
          Last seen {e.last_activity_at ? fmtDateTime(e.last_activity_at) : "never"}. Engagement is for information only; it does not affect the certificate.
        </p>
      </section>
      {block.joining_date && (
        <p className="text-xs text-muted-foreground">
          Joined {fmtDate(block.joining_date)}. Figures as of {fmtDateTime(block.as_of)}.
        </p>
      )}
    </div>
  );
}
