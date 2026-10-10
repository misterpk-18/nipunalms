/** Everything an Academic Coordinator or Branch Manager does to one batch: edit, state, readiness, trainers, students, history. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type BatchDetail, type Check } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { DataTable, KeyValue, Note, PillTabs, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { ActionDialog, StateBadge, fmtDate, fmtDay, useCanManage } from "@/features/shared/delivery-ui";
import { timetableLabel } from "@/features/academic/timetable";
import { RosterDialog, useDelivery } from "@/features/shared/sessions";
import { EditBatchDialog, HandoverDialog, LifecycleActions, RequestTransferDialog, RequestsTab } from "./batch-operations";

const TABS = ["Overview", "Readiness", "Trainers", "Students", "Requests", "History"] as const;
const CHECK_TONE = { pass: "success", fail: "danger", pending: "warning", warn: "warning" } as const;
const CHECK_WORD = { pass: "Pass", fail: "Fail", pending: "Pending", warn: "Review" } as const;

export function CheckList({ checks }: { checks: Check[] }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {checks.map((c) => (
        <li key={c.key} className="rounded-lg border p-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">{c.label}</span>
            <StatusBadge tone={CHECK_TONE[c.status]}>{CHECK_WORD[c.status]}</StatusBadge>
          </div>
          <p className="mt-1 text-muted-foreground">{c.detail}</p>
        </li>
      ))}
    </ul>
  );
}

function Overview({ batch, manager }: { batch: BatchDetail; manager: boolean }) {
  const closed = ["Completed", "Cancelled", "Archived"].includes(batch.state);
  const sides = [
    batch.classroom_capacity != null && `classroom ${batch.classroom_capacity}`,
    batch.lab_capacity != null && `lab ${batch.lab_capacity}`,
    batch.online_capacity != null && `online ${batch.online_capacity}`,
  ].filter(Boolean);
  return (
    <>
      <KeyValue
        items={[
          [
            "Batch ID",
            <span key="i" className="font-mono text-xs">
              {batch.batch_code}
            </span>,
          ],
          ["Display name", batch.display_name ?? "—"],
          ["Course", `${batch.course.course_code} — ${batch.course.title}${batch.component ? ` (${batch.component.track_name} track)` : ""}`],
          ["Branch", batch.branch.branch_name],
          ["Created at", batch.creating_branch.branch_name],
          ["Type and pattern", `${batch.batch_type} · ${batch.schedule_pattern}`],
          ["Curriculum version", batch.curriculum_version?.version_label ?? "No approved curriculum yet"],
          ["Seats", `${batch.allocated_count} of ${batch.capacity}${batch.is_full ? " (full)" : ""}${sides.length ? ` · ${sides.join(" · ")}` : ""}`],
          ["Mode", batch.mode],
          ["Planned dates", `${fmtDay(batch.planned_start)} → ${fmtDay(batch.planned_end)}`],
          ["Timetable", timetableLabel(batch)],
          ["Recording", batch.recording_provision ? `${batch.recording_provision}${batch.recording_terms ? ` — ${batch.recording_terms}` : ""}` : "Not set"],
          ["Meet series", batch.meet_series_link ?? "Not set"],
          ["Sessions", `${batch.session_counts.delivered} delivered · ${batch.session_counts.upcoming} upcoming · ${batch.session_counts.cancelled} cancelled`],
          [
            "State",
            <span key="s" className="inline-flex flex-wrap items-center gap-2">
              <StateBadge label={batch.state_label} />
              {batch.state === "On Hold" && batch.held_from_state && <span className="text-xs text-muted-foreground">held from {batch.held_from_state}</span>}
            </span>,
          ],
          ["Proposed", batch.proposed_by ? `${batch.proposed_by.full_name}, ${batch.proposed_at ? fmtDate(batch.proposed_at) : ""}${batch.proposal_note ? ` — ${batch.proposal_note}` : ""}` : "—"],
          ["Confirmed", batch.confirmed_by ? `${batch.confirmed_by.full_name}, ${batch.confirmed_at ? fmtDate(batch.confirmed_at) : ""}` : "—"],
          ["Readiness", <StatusBadge key="r">{batch.readiness}</StatusBadge>],
        ]}
      />
      {manager && !closed && (
        <div className="mt-4">
          <EditBatchDialog batch={batch} />
        </div>
      )}
      <LifecycleActions batch={batch} />
    </>
  );
}

function ReadinessTab({ batch, manager }: { batch: BatchDetail; manager: boolean }) {
  const query = useQuery({ queryKey: ["delivery", "readiness", batch.batch_id, batch.readiness], queryFn: () => deliveryApi.readiness(batch.batch_id) });
  const set = useDelivery(
    (body: { readiness: string; readiness_reason?: string | null; recovery_owner?: string | null }) => deliveryApi.setReadiness(batch.batch_id, body),
    "Readiness updated",
  );
  return (
    <QueryView query={query}>
      {(r) => (
        <div className="space-y-3">
          <p className="text-sm">
            Recorded: <StatusBadge>{r.readiness}</StatusBadge>
            {r.readiness_reason && <span className="ml-2 text-muted-foreground">{r.readiness_reason}</span>}
            {r.recovery_owner && <span className="ml-2 text-muted-foreground">· Recovery owner: {r.recovery_owner}</span>}
          </p>
          <CheckList checks={r.checks} />
          <h3 className="pt-2 text-sm font-semibold">Readiness record (7 points)</h3>
          <p className="text-sm text-muted-foreground">Points 1 to 6 must pass before the batch can be proposed; point 7 is advisory.</p>
          <CheckList checks={r.checklist} />
          <p className="text-sm">
            The checks suggest: <StatusBadge>{r.suggested.readiness}</StatusBadge>
          </p>
          {manager && (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={r.suggested.readiness === r.readiness && r.suggested.readiness_reason === r.readiness_reason}
                onClick={() => set.mutate(r.suggested)}
              >
                Apply suggested readiness
              </Button>
              <ActionDialog
                trigger={
                  <Button size="sm" variant="outline">
                    Set manually
                  </Button>
                }
                title="Set readiness"
                description="Blocked needs a reason and a recovery owner; Ready is only accepted when the required checks pass."
                fields={[
                  {
                    name: "readiness",
                    label: "Readiness",
                    type: "select",
                    options: ["Ready", "Blocked", "Pending Verification"].map((v) => ({ value: v, label: v })),
                    value: r.readiness,
                  },
                  { name: "reason", label: "Reason", type: "textarea" },
                  { name: "owner", label: "Recovery owner" },
                ]}
                onSubmit={(v) => set.mutateAsync({ readiness: v["readiness"]!, readiness_reason: v["reason"] || null, recovery_owner: v["owner"] || null })}
              />
            </div>
          )}
        </div>
      )}
    </QueryView>
  );
}

function TrainersTab({ batch, manager }: { batch: BatchDetail; manager: boolean }) {
  const staff = useQuery({
    queryKey: ["delivery", "trainers", batch.branch.branch_id],
    queryFn: () => deliveryApi.staff("TRAINER", batch.branch.branch_id),
    enabled: manager,
  });
  const assign = useDelivery((v: { trainer_user_id: number; role: string }) => deliveryApi.assignTrainer(batch.batch_id, v), "Trainer assigned");
  const role = useDelivery((v: { id: number; role: string }) => deliveryApi.trainerRole(batch.batch_id, v.id, v.role), "Trainer role updated");
  const end = useDelivery((id: number) => deliveryApi.endTrainer(batch.batch_id, id), "Assignment ended");
  const assigned = new Set(batch.trainers.map((t) => t.user_id));
  return (
    <>
      <DataTable
        caption="Trainers"
        rows={batch.trainers}
        getKey={(t) => t.batch_trainer_id}
        empty="No trainer is assigned yet."
        cols={[
          { h: "Trainer", c: (t) => t.full_name },
          { h: "Role", c: (t) => <StatusBadge tone={t.role === "Lead" ? "info" : "neutral"}>{t.role}</StatusBadge> },
          { h: "Since", c: (t) => fmtDay(t.from_date) },
          ...(manager
            ? [
                {
                  h: "Actions",
                  c: (t: (typeof batch.trainers)[number]) => (
                    <div className="flex flex-wrap gap-1.5">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => role.mutate({ id: t.batch_trainer_id, role: t.role === "Lead" ? "Co-trainer" : "Lead" })}
                      >
                        {t.role === "Lead" ? "Make co-trainer" : "Make lead"}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => end.mutate(t.batch_trainer_id)}>
                        End assignment
                      </Button>
                    </div>
                  ),
                },
              ]
            : []),
        ]}
      />
      {manager && (
        <div className="mt-3">
          <ActionDialog
            trigger={<Button size="sm">Assign trainer</Button>}
            title="Assign a trainer"
            description="Only people holding the Trainer role at this branch can be assigned."
            fields={[
              {
                name: "trainer_user_id",
                label: "Trainer",
                type: "select",
                required: true,
                options: (staff.data ?? []).filter((s) => !assigned.has(s.user_id)).map((s) => ({ value: s.user_id, label: s.full_name })),
              },
              {
                name: "role",
                label: "Role",
                type: "select",
                options: [
                  { value: "Lead", label: "Lead" },
                  { value: "Co-trainer", label: "Co-trainer" },
                ],
                value: batch.trainers.some((t) => t.role === "Lead") ? "Co-trainer" : "Lead",
              },
            ]}
            onSubmit={(v) => assign.mutateAsync({ trainer_user_id: Number(v["trainer_user_id"]), role: v["role"]! })}
          />
        </div>
      )}
    </>
  );
}

function StudentsTab({ batch, manager }: { batch: BatchDetail; manager: boolean }) {
  const [history, setHistory] = useState(false);
  const roster = useQuery({
    queryKey: ["delivery", "roster", batch.batch_id, history],
    queryFn: () => deliveryApi.roster(batch.batch_id, history ? {} : { status: "Active" }),
  });
  const others = useQuery({
    queryKey: ["delivery", "batches", "same-course", batch.course.course_id, batch.branch.branch_id],
    queryFn: () => deliveryApi.batches({ course_id: batch.course.course_id, branch_id: batch.branch.branch_id }),
    enabled: manager,
  });
  const deallocate = useDelivery(
    (v: { enrolmentId: number; reason: string; trackId: number | null }) => deliveryApi.deallocate(v.enrolmentId, v.reason, v.trackId),
    "Student removed from the batch",
  );
  const enrolments = useQuery({
    queryKey: ["delivery", "enrolments", "batch", batch.batch_id],
    queryFn: () => deliveryApi.enrolments({ batch_id: batch.batch_id }),
    enabled: manager,
  });
  const targets = (others.data?.data ?? []).filter((b) => b.batch_id !== batch.batch_id && !["Completed", "Cancelled", "Archived"].includes(b.state));
  return (
    <>
      <label className="mb-3 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={history} onChange={(e) => setHistory(e.target.checked)} /> Include ended and transferred allocations
      </label>
      <QueryView query={roster}>
        {(page) => (
          <DataTable
            caption="Students"
            rows={page.data}
            getKey={(r) => r.allocation_id}
            empty="No students allocated yet."
            cols={[
              { h: "Student", c: (r) => `${r.student.full_name} (${r.student.student_code})` },
              { h: "Enrolment", c: (r) => `${r.enrolment.enrolment_code} · ${r.enrolment.status}${r.enrolment_track_id ? " · track seat" : ""}` },
              {
                h: "Seat",
                c: (r) => (
                  <>
                    <StatusBadge>{r.status}</StatusBadge>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {fmtDay(r.effective_from)}
                      {r.effective_to ? ` → ${fmtDay(r.effective_to)}` : ""}
                      {r.reason ? ` · ${r.reason}` : ""}
                    </div>
                  </>
                ),
              },
              ...(manager
                ? [
                    {
                      h: "Actions",
                      c: (r: (typeof page.data)[number]) =>
                        r.status === "Active" ? (
                          <div className="flex flex-wrap gap-1.5">
                            <RequestTransferDialog
                              row={r}
                              targets={targets}
                              enrolment={enrolments.data?.data.find((e) => e.enrolment_id === r.enrolment_id)}
                            />
                            <HandoverDialog batch={batch} row={r} targets={targets} />
                            <ActionDialog
                              trigger={
                                <Button size="sm" variant="outline">
                                  Deallocate
                                </Button>
                              }
                              title={`Remove ${r.student.full_name} from ${batch.batch_code}`}
                              fields={[{ name: "reason", label: "Reason", type: "textarea", required: true }]}
                              submitLabel="Deallocate"
                              onSubmit={(v) => deallocate.mutateAsync({ enrolmentId: r.enrolment_id, reason: v["reason"]!, trackId: r.enrolment_track_id })}
                            />
                          </div>
                        ) : (
                          "—"
                        ),
                    },
                  ]
                : []),
            ]}
          />
        )}
      </QueryView>
    </>
  );
}

export function BatchPanel({ batchId }: { batchId: number }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const manager = useCanManage();
  const query = useQuery({ queryKey: ["delivery", "batch", batchId], queryFn: () => deliveryApi.batch(batchId) });
  return (
    <QueryView query={query}>
      {(batch) => (
        <Section title={`${batch.batch_code} — ${batch.display_name ?? batch.course.title}`} actions={<RosterDialog batch={batch} />}>
          {batch.readiness !== "Ready" && (
            <p className="mb-3 text-sm">
              <StatusBadge>{batch.readiness}</StatusBadge> {batch.readiness_reason} {batch.recovery_owner && `· Recovery owner: ${batch.recovery_owner}`}
            </p>
          )}
          <PillTabs label="Batch sections" tabs={TABS} value={tab} onChange={setTab} />
          {tab === "Overview" && <Overview batch={batch} manager={manager} />}
          {tab === "Readiness" && <ReadinessTab batch={batch} manager={manager} />}
          {tab === "Trainers" && <TrainersTab batch={batch} manager={manager} />}
          {tab === "Students" && <StudentsTab batch={batch} manager={manager} />}
          {tab === "Requests" && <RequestsTab batch={batch} />}
          {tab === "History" && (
            <>
              <ul className="space-y-1 text-sm">
                {batch.history.map((e) => (
                  <li key={e.event_id}>
                    {fmtDate(e.created_at)} · <strong>{e.event_type}</strong>
                    {e.from_value || e.to_value ? ` (${e.from_value ?? "—"} → ${e.to_value ?? "—"})` : ""} by {e.actor?.full_name ?? "system"}
                    {e.reason ? ` — ${e.reason}` : ""}
                  </li>
                ))}
                {batch.history.length === 0 && <li className="text-muted-foreground">No changes recorded.</li>}
              </ul>
              <div className="mt-3">
                <Note>State, readiness, trainer and curriculum changes are logged with who made them and why.</Note>
              </div>
            </>
          )}
        </Section>
      )}
    </QueryView>
  );
}
