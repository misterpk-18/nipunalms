/** The parts of a batch page: overview, readiness checks, trainers and students (the page itself is `features/shared/batch-page`). */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type BatchDetail, type Check } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { DataTable, KeyValue, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { statusInfo } from "@/lib/status";
import { ActionDialog, StateBadge, fmtDate, fmtDay } from "@/features/shared/delivery-ui";
import { timetableLabel } from "./timetable";
import { useDelivery } from "@/features/shared/sessions";
import { EditBatchDialog, HandoverDialog, LifecycleActions, RequestTransferDialog } from "./batch-operations";

const CHECK_TONE = { pass: "success", fail: "danger", pending: "neutral", warn: "warning" } as const;
const CHECK_WORD = { pass: "Pass", fail: "Fail", pending: "Pending", warn: "Review" } as const;

export function CheckList({ checks }: { checks: Check[] }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {checks.map((c) => (
        <li key={c.key} className="rounded-lg border p-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">{c.label}</span>
            <Tag tone={CHECK_TONE[c.status]}>{CHECK_WORD[c.status]}</Tag>
          </div>
          <p className="mt-1 text-muted-foreground">{c.detail}</p>
        </li>
      ))}
    </ul>
  );
}

export function Overview({ batch, manage, approve }: { batch: BatchDetail; manage: boolean; approve: boolean }) {
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
          [
            "Proposed",
            batch.proposed_by
              ? `${batch.proposed_by.full_name}, ${batch.proposed_at ? fmtDate(batch.proposed_at) : ""}${batch.proposal_note ? ` — ${batch.proposal_note}` : ""}`
              : "—",
          ],
          ["Confirmed", batch.confirmed_by ? `${batch.confirmed_by.full_name}, ${batch.confirmed_at ? fmtDate(batch.confirmed_at) : ""}` : "—"],
          ["Checks", <StatusBadge key="r" domain="readiness" code={batch.readiness} />],
        ]}
      />
      {manage && !closed && (
        <div className="mt-4">
          <EditBatchDialog batch={batch} />
        </div>
      )}
      <LifecycleActions batch={batch} manage={manage} approve={approve} />
    </>
  );
}

export function ReadinessTab({ batch, manage }: { batch: BatchDetail; manage: boolean }) {
  const query = useQuery({ queryKey: ["delivery", "readiness", batch.batch_id, batch.readiness], queryFn: () => deliveryApi.readiness(batch.batch_id) });
  const set = useDelivery(
    (body: { readiness: string; readiness_reason?: string | null; recovery_owner?: string | null }) => deliveryApi.setReadiness(batch.batch_id, body),
    "Batch status updated",
  );
  return (
    <QueryView query={query}>
      {(r) => (
        <div className="space-y-3">
          <p className="text-sm">
            Recorded: <StatusBadge domain="readiness" code={r.readiness} />
            {r.readiness_reason && <span className="ml-2 text-muted-foreground">{r.readiness_reason}</span>}
            {r.recovery_owner && <span className="ml-2 text-muted-foreground">· Owner: {r.recovery_owner}</span>}
          </p>
          <CheckList checks={r.checks} />
          <h3 className="pt-2 text-sm font-semibold">Checklist before confirming (7 points)</h3>
          <p className="text-sm text-muted-foreground">Points 1 to 6 must pass before the batch can be confirmed; point 7 is the confirmation itself.</p>
          <CheckList checks={r.checklist} />
          <p className="text-sm">
            The checks suggest: <StatusBadge domain="readiness" code={r.suggested.readiness} />
          </p>
          {manage && (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={r.suggested.readiness === r.readiness && r.suggested.readiness_reason === r.readiness_reason}
                onClick={() => set.mutate(r.suggested)}
              >
                Update the status from the checks
              </Button>
              <ActionDialog
                trigger={
                  <Button size="sm" variant="outline">
                    Set manually
                  </Button>
                }
                title="Set the batch status"
                description="Blocked needs a reason and an owner; Ready is only accepted when the required checks pass."
                fields={[
                  {
                    name: "readiness",
                    label: "Status",
                    type: "select",
                    options: ["Ready", "Blocked", "Pending Verification"].map((v) => ({ value: v, label: statusInfo("readiness", v).label })),
                    value: r.readiness,
                  },
                  { name: "reason", label: "Reason", type: "textarea" },
                  { name: "owner", label: "Owner" },
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

export function TrainersTab({ batch, manage }: { batch: BatchDetail; manage: boolean }) {
  const staff = useQuery({
    queryKey: ["delivery", "trainers", batch.branch.branch_id],
    queryFn: () => deliveryApi.staff("TRAINER", batch.branch.branch_id),
    enabled: manage,
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
          { h: "Role", c: (t) => <Tag tone={t.role === "Lead" ? "info" : "neutral"}>{t.role}</Tag> },
          { h: "Since", c: (t) => fmtDay(t.from_date) },
          ...(manage
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
      {manage && (
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

export function StudentsTab({ batch, manage }: { batch: BatchDetail; manage: boolean }) {
  const [history, setHistory] = useState(false);
  const roster = useQuery({
    queryKey: ["delivery", "roster", batch.batch_id, history],
    queryFn: () => deliveryApi.roster(batch.batch_id, history ? {} : { status: "Active" }),
  });
  const others = useQuery({
    queryKey: ["delivery", "batches", "same-course", batch.course.course_id, batch.branch.branch_id],
    queryFn: () => deliveryApi.batches({ course_id: batch.course.course_id, branch_id: batch.branch.branch_id }),
    enabled: manage,
  });
  const deallocate = useDelivery(
    (v: { enrolmentId: number; reason: string; trackId: number | null }) => deliveryApi.deallocate(v.enrolmentId, v.reason, v.trackId),
    "Student removed from the batch",
  );
  const enrolments = useQuery({
    queryKey: ["delivery", "enrolments", "batch", batch.batch_id],
    queryFn: () => deliveryApi.enrolments({ batch_id: batch.batch_id }),
    enabled: manage,
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
                    <StatusBadge domain="seat" code={r.status} />
                    <div className="mt-1 text-xs text-muted-foreground">
                      {fmtDay(r.effective_from)}
                      {r.effective_to ? ` → ${fmtDay(r.effective_to)}` : ""}
                      {r.reason ? ` · ${r.reason}` : ""}
                    </div>
                  </>
                ),
              },
              ...(manage
                ? [
                    {
                      h: "Actions",
                      c: (r: (typeof page.data)[number]) =>
                        r.status === "Active" ? (
                          <div className="flex flex-wrap gap-1.5">
                            <RequestTransferDialog row={r} targets={targets} enrolment={enrolments.data?.data.find((e) => e.enrolment_id === r.enrolment_id)} />
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
