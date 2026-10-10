/** Meet operations: one day of classes with link and host readiness, delays, attendance and log state, and the open work around them. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type MeetOpsRow } from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, Grid, Note, PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { fmtDate, fmtRange, mono } from "@/features/shared/delivery-ui";
import { todayIso } from "@/lib/format";
import { ClassOperationsDialog, ResolveDisruptionDialog } from "./class-operations";
import { useCanManage } from "@/features/shared/delivery-ui";

const JOB_LABELS: Record<string, string> = {
  "session-delay-check": "Delayed or failed starts",
  "class-log-check": "Missing class logs",
  "attendance-unconfirmed": "Attendance not confirmed",
  "recording-check": "Recordings",
};

function Tile({ label, value, tone }: { label: string; value: number | string; tone?: "warning" }) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={tone === "warning" && Number(value) > 0 ? "text-2xl font-semibold text-warning" : "text-2xl font-semibold"}>{value}</p>
    </div>
  );
}

const linkCell = (r: MeetOpsRow) =>
  r.link_ready === null ? "—" : r.link_ready ? <StatusBadge domain="meet" code="Linked" /> : <Tag tone="warning">{r.meet_status_label ?? "No link"}</Tag>;

export function MeetOperations() {
  const { profile } = useAuth();
  const manager = useCanManage();
  const [date, setDate] = useState(todayIso());
  const [branch, setBranch] = useState("");
  const branches = profile?.allowed_branches ?? [];
  const query = useQuery({
    queryKey: ["delivery", "meet-operations", date, branch],
    queryFn: () => deliveryApi.meetOperations({ date: date || undefined, branch_id: branch || undefined }),
  });
  return (
    <>
      <PageHead title="Meet Operations" description="Today's live classes: is the link ready, who hosts, what went wrong, and what is still owed." />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Input type="date" aria-label="Date" value={date} onChange={(e) => setDate(e.target.value)} />
        {branches.length > 1 && (
          <NativeSelect
            aria-label="Filter by branch"
            placeholder="All branches"
            options={branches.map((b) => ({ value: b.branch_id, label: b.branch_name }))}
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
          />
        )}
      </div>
      <QueryView query={query}>
        {(ops) => (
          <div className="space-y-6">
            <Grid cols={4}>
              <Tile label="Classes" value={ops.summary.classes} />
              <Tile label="Online, not ready" value={ops.summary.online_not_ready} tone="warning" />
              <Tile label="Delayed or disrupted" value={ops.summary.delayed_or_disrupted} tone="warning" />
              <Tile label="Attendance awaiting" value={ops.summary.attendance_awaiting} tone="warning" />
            </Grid>

            <Section title={`Classes on ${fmtDate(ops.date)}`}>
              <DataTable
                caption="Classes of the day"
                rows={ops.sessions}
                getKey={(r) => r.session_id}
                empty="No class is scheduled on this day."
                cols={[
                  { h: "When (IST)", c: (r) => fmtRange(r.starts_at, r.ends_at).split(" · ").pop() ?? "" },
                  {
                    h: "Class",
                    c: (r) => (
                      <>
                        <div className="font-medium">{r.title}</div>
                        <div className="text-xs text-muted-foreground">
                          {r.session_code} · {r.batch.batch_code} · {r.mode}
                          {r.purpose !== "Regular" ? ` · ${r.purpose}` : ""}
                        </div>
                      </>
                    ),
                  },
                  { h: "Link", c: linkCell },
                  {
                    h: "Host / backup",
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
                        {r.attendance.awaiting_confirmation && <div><Tag tone="warning">Awaiting the trainer</Tag></div>}
                      </>
                    ),
                  },
                  { h: "Recording", c: (r) => (r.recording.length ? r.recording.join(", ") : "—") },
                  { h: "Class log", c: (r) => (r.log_overdue ? <StatusBadge domain="exception" code="Overdue" /> : <span className="text-muted-foreground">{r.state_label}</span>) },
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
                    { h: "Class", c: (d) => <>{d.session.title}<div className="text-xs text-muted-foreground">{d.session.session_code} · {d.session.batch.batch_code}</div></> },
                    { h: "Kind", c: (d) => <>{d.kind}{d.raised_by_job && <div className="text-xs text-muted-foreground">Raised by the delay check</div>}</> },
                    { h: "Since", c: (d) => fmtDate(d.detected_at) },
                    ...(manager ? [{ h: "", c: (d: (typeof ops.open_disruptions)[number]) => <ResolveDisruptionDialog disruption={d} /> }] : []),
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
                    { h: "Cancelled class", c: (s) => <>{s.title}<div className="text-xs text-muted-foreground">{s.session_code}</div></> },
                    { h: "Batch", c: (s) => mono(s.batch.batch_code) },
                    { h: "Was", c: (s) => fmtDate(s.starts_at) },
                  ]}
                />
              </Section>
              <Section title="Classes awaiting approval">
                <DataTable
                  caption="Classes awaiting approval"
                  rows={ops.awaiting_approval}
                  getKey={(s) => s.session_id}
                  empty="No replacement, remedial or extra class awaits approval."
                  cols={[
                    { h: "Class", c: (s) => <>{s.title}<div className="text-xs text-muted-foreground">{s.session_code}</div></> },
                    { h: "Purpose", c: (s) => s.purpose },
                    { h: "Batch", c: (s) => mono(s.batch.batch_code) },
                    { h: "When", c: (s) => fmtDate(s.starts_at) },
                  ]}
                />
                <p className="mt-2 text-xs text-muted-foreground">A Branch Manager approves these from the Schedule page.</p>
              </Section>
              <Section title="Missing class logs">
                <DataTable
                  caption="Missing class logs"
                  rows={ops.missing_logs}
                  getKey={(s) => s.session_id}
                  empty="No class log is overdue."
                  cols={[
                    { h: "Class", c: (s) => <>{s.title}<div className="text-xs text-muted-foreground">{s.session_code}</div></> },
                    { h: "Trainer", c: (s) => s.trainer },
                    { h: "Batch", c: (s) => mono(s.batch.batch_code) },
                    { h: "Was", c: (s) => fmtDate(s.starts_at) },
                  ]}
                />
              </Section>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Section title="Evidence to review">
                <dl className="space-y-1 text-sm">
                  <div>
                    <dt className="inline text-muted-foreground">Unmatched Meet participants: </dt>
                    <dd className="inline font-medium">{ops.unmatched_participants}</dd>
                  </div>
                  <div>
                    <dt className="inline text-muted-foreground">Open recording issues: </dt>
                    <dd className="inline font-medium">{ops.open_recording_issues}</dd>
                  </div>
                </dl>
                <p className="mt-2 text-xs text-muted-foreground">Review an unmatched participant from the class's Participation tab. Participation is evidence, never attendance.</p>
              </Section>
              <Section title="Meet integration">
                <p className="mb-2">
                  <StatusBadge domain="integration" code={ops.integration.verified ? "Verified" : "Not Verified"} />
                </p>
                <p className="text-sm">{ops.integration.note}</p>
              </Section>
            </div>

            <Section title="Last background checks">
              <DataTable
                caption="Last background checks"
                rows={ops.last_runs}
                getKey={(j) => j.job_name}
                cols={[
                  { h: "Check", c: (j) => JOB_LABELS[j.job_name] ?? j.job_name },
                  { h: "Last succeeded", c: (j) => (j.last_ok_at ? fmtDate(j.last_ok_at) + " " + new Date(j.last_ok_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" }) + " IST" : <Tag tone="warning">Not yet</Tag>) },
                ]}
              />
            </Section>
            <Note>The LMS records Meet state, hosts, incidents and participation; it never calls Google until the integration is verified. Times are IST.</Note>
          </div>
        )}
      </QueryView>
    </>
  );
}
