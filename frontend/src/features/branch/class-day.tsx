/** Class day: today's classes, each ready or not; the tiles filter the list and a missing Meet link is set right here. */
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type MeetOpsRow } from "@/api/delivery";
import { useActing } from "@/auth/acting";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ClassOperationsDialog, ResolveDisruptionDialog } from "@/features/academic/class-operations";
import { fmtDate, fmtRange, mono, useCanManage } from "@/features/shared/delivery-ui";
import { todayIso } from "@/lib/format";
import { cn } from "@/lib/utils";
import { MeetLinkDialog } from "./class-actions";
import { BranchPicker } from "./my-work";

const OPEN = ["Scheduled", "Rescheduled", "Live"];
type Filter = "all" | "link" | "disrupted" | "attendance" | "log";

const FILTERS: { key: Filter; label: string; test: (r: MeetOpsRow) => boolean }[] = [
  { key: "all", label: "All classes", test: () => true },
  { key: "link", label: "Meet link missing", test: (r) => r.link_ready === false && OPEN.includes(r.state) },
  { key: "disrupted", label: "Delayed or disrupted", test: (r) => !!r.disruption || !!r.delay_notice_at },
  { key: "attendance", label: "Attendance to mark", test: (r) => r.attendance.awaiting_confirmation },
  { key: "log", label: "Class log overdue", test: (r) => r.log_overdue },
];

function FilterTile({ label, count, active, onClick }: { label: string; count: number; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn("rounded-xl border bg-card p-4 text-left shadow-sm hover:bg-accent", active && "border-primary ring-2 ring-primary/30")}
    >
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("text-2xl font-semibold tabular-nums", count > 0 && label !== "All classes" && "text-warning")}>{count}</p>
    </button>
  );
}

function LinkCell({ row, manage }: { row: MeetOpsRow; manage: boolean }) {
  if (row.link_ready === null) return <span className="text-muted-foreground">Classroom</span>;
  if (row.link_ready) return <StatusBadge domain="meet" code="Linked" />;
  const settable = manage && OPEN.includes(row.state);
  return (
    <div className="space-y-1">
      <Tag tone="warning">{row.meet_status_label ?? "No link"}</Tag>
      {settable && (
        <div>
          <MeetLinkDialog
            session={{ session_id: row.session_id, title: row.title }}
            trigger={
              <Button size="sm" variant="outline">
                Add Meet link
              </Button>
            }
          />
        </div>
      )}
    </div>
  );
}

export function ClassDay() {
  const manage = useCanManage();
  const { branchId } = useActing("branch");
  const [date, setDate] = useState(todayIso());
  const [filter, setFilter] = useState<Filter>("all");
  const query = useQuery({
    queryKey: ["delivery", "meet-operations", date, branchId],
    queryFn: () => deliveryApi.meetOperations({ date: date || undefined, branch_id: branchId }),
  });
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHead
        title="Class day"
        description="The day's classes: is each link ready, who hosts, what went wrong and what is still owed. Pick a tile to filter the list."
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/branch/recordings">Recordings</Link>
            </Button>
            <BranchPicker />
          </>
        }
      />
      <div className="max-w-xs">
        <Input type="date" aria-label="Date" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      <QueryView query={query}>
        {(ops) => {
          const active = FILTERS.find((f) => f.key === filter)!;
          const rows = ops.sessions.filter(active.test);
          return (
            <div className="space-y-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" role="group" aria-label="Filter the day's classes">
                {FILTERS.map((f) => (
                  <FilterTile
                    key={f.key}
                    label={f.label}
                    count={ops.sessions.filter(f.test).length}
                    active={filter === f.key}
                    onClick={() => setFilter(f.key)}
                  />
                ))}
              </div>

              <Section title={`${active.label} on ${fmtDate(`${ops.date}T12:00:00+05:30`)}`}>
                <DataTable
                  caption="Classes of the day"
                  rows={rows}
                  getKey={(r) => r.session_id}
                  empty={
                    filter === "all"
                      ? "No class is scheduled on this day. Classes appear here once they are created from a batch's timetable."
                      : "No class matches this filter."
                  }
                  emptyAction={
                    filter === "all" ? (
                      <Button asChild size="sm" variant="outline">
                        <Link to="/branch/schedule">Open Schedule</Link>
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => setFilter("all")}>
                        Show all classes
                      </Button>
                    )
                  }
                  cols={[
                    { h: "When (IST)", c: (r) => fmtRange(r.starts_at, r.ends_at).split(" · ").pop() ?? "" },
                    {
                      h: "Class",
                      c: (r) => (
                        <>
                          <div className="font-medium">{r.title}</div>
                          <div className="text-xs text-muted-foreground">
                            {r.batch.display_name ?? r.batch.batch_code} · {r.mode}
                            {r.purpose !== "Regular" ? ` · ${r.purpose} class` : ""}
                          </div>
                        </>
                      ),
                    },
                    { h: "Meet link", c: (r) => <LinkCell row={r} manage={manage} /> },
                    {
                      h: "Host and backup",
                      c: (r) =>
                        r.host === null ? (
                          "—"
                        ) : (
                          <>
                            <div>{r.host}</div>
                            <div className="text-xs text-muted-foreground">{r.backup ? `Backup: ${r.backup}` : "No backup named"}</div>
                          </>
                        ),
                    },
                    {
                      h: "Delay or disruption",
                      c: (r) =>
                        r.disruption ? (
                          <>
                            <Tag tone="danger">{r.disruption.kind}</Tag>
                            {r.disruption.delay_minutes != null && <div className="text-xs text-muted-foreground">{r.disruption.delay_minutes} min</div>}
                          </>
                        ) : r.delay_notice_at ? (
                          <Tag tone="warning">Delay noticed</Tag>
                        ) : (
                          "None"
                        ),
                    },
                    {
                      h: "Attendance",
                      c: (r) => (
                        <>
                          {r.attendance.marked} of {r.attendance.seats}
                          {r.attendance.awaiting_confirmation && (
                            <div>
                              <Tag tone="warning">Waiting for the trainer</Tag>
                            </div>
                          )}
                        </>
                      ),
                    },
                    { h: "Recording", c: (r) => (r.recording.length ? r.recording.join(", ") : "—") },
                    {
                      h: "Class log",
                      c: (r) =>
                        r.log_overdue ? <StatusBadge domain="exception" code="Overdue" /> : <span className="text-muted-foreground">{r.state_label}</span>,
                    },
                    { h: "", c: (r) => <ClassOperationsDialog target={{ ...r, branch: r.branch }} /> },
                  ]}
                />
              </Section>

              <div className="grid gap-6 lg:grid-cols-2">
                <Section title="Open disruptions">
                  <DataTable
                    caption="Open disruptions"
                    rows={ops.open_disruptions}
                    getKey={(d) => d.disruption_id}
                    empty="No open disruption."
                    cols={[
                      {
                        h: "Class",
                        c: (d) => (
                          <>
                            {d.session.title}
                            <div className="text-xs text-muted-foreground">{d.session.batch.batch_code}</div>
                          </>
                        ),
                      },
                      {
                        h: "What happened",
                        c: (d) => (
                          <>
                            {d.kind}
                            {d.raised_by_job && <div className="text-xs text-muted-foreground">Found by the delay check</div>}
                          </>
                        ),
                      },
                      { h: "Since", c: (d) => fmtDate(d.detected_at) },
                      ...(manage ? [{ h: "", c: (d: (typeof ops.open_disruptions)[number]) => <ResolveDisruptionDialog disruption={d} /> }] : []),
                    ]}
                  />
                </Section>
                <Section title="Replacements owed">
                  <DataTable
                    caption="Replacements owed"
                    rows={ops.replacements_owed}
                    getKey={(s) => s.session_id}
                    empty="No cancelled class owes a replacement."
                    cols={[
                      { h: "Cancelled class", c: (s) => s.title },
                      { h: "Batch", c: (s) => mono(s.batch.batch_code) },
                      { h: "Was", c: (s) => fmtDate(s.starts_at) },
                    ]}
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    Plan a replacement from{" "}
                    <Link to="/branch/schedule" search={{ view: "list" }} className="text-primary underline-offset-2 hover:underline">
                      Schedule
                    </Link>
                    .
                  </p>
                </Section>
                <Section title="Classes waiting for approval">
                  <DataTable
                    caption="Classes waiting for approval"
                    rows={ops.awaiting_approval}
                    getKey={(s) => s.session_id}
                    empty="No extra, remedial or replacement class is waiting."
                    cols={[
                      { h: "Class", c: (s) => s.title },
                      { h: "Kind", c: (s) => s.purpose },
                      { h: "Batch", c: (s) => mono(s.batch.batch_code) },
                      { h: "When", c: (s) => fmtDate(s.starts_at) },
                    ]}
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    Decide on{" "}
                    <Link to="/branch/schedule" search={{ decide: 1 }} className="text-primary underline-offset-2 hover:underline">
                      Schedule
                    </Link>
                    .
                  </p>
                </Section>
                <Section title="Class logs not written">
                  <DataTable
                    caption="Class logs not written"
                    rows={ops.missing_logs}
                    getKey={(s) => s.session_id}
                    empty="No class log is overdue."
                    cols={[
                      { h: "Class", c: (s) => s.title },
                      { h: "Trainer", c: (s) => s.trainer },
                      { h: "Batch", c: (s) => mono(s.batch.batch_code) },
                      { h: "Was", c: (s) => fmtDate(s.starts_at) },
                    ]}
                  />
                </Section>
              </div>

              <Section title="Evidence to review">
                <dl className="space-y-1 text-sm">
                  <div>
                    <dt className="inline text-muted-foreground">Meet participants not matched to a student: </dt>
                    <dd className="inline font-medium">{ops.unmatched_participants}</dd>
                  </div>
                  <div>
                    <dt className="inline text-muted-foreground">Recording problems still open: </dt>
                    <dd className="inline font-medium">{ops.open_recording_issues}</dd>
                  </div>
                </dl>
                <p className="mt-2 text-xs text-muted-foreground">
                  Review an unmatched participant from the class's Manage window, under Participation. Joining a Meet is evidence, never attendance.
                </p>
              </Section>
              <HowThisWorks>
                <p>
                  The LMS records Meet links, hosts, incidents and who joined. It does not call Google until the Meet connection is checked in Setup and health.
                </p>
                <p>Times are IST. The trainer starts and logs each class from their Today screen.</p>
              </HowThisWorks>
            </div>
          );
        }}
      </QueryView>
    </div>
  );
}
