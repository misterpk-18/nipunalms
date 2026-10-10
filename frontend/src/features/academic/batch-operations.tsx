/**
 * Batch operations: the lifecycle buttons for each state and role, the edit dialog, and the request records
 * of one batch: capacity increases, student transfers, material changes with each student's agreement, merge / split
 * and completion handovers.
 */
import { useQuery } from "@tanstack/react-query";
import {
  CHANGE_KINDS,
  deliveryApi,
  type Batch,
  type BatchDetail,
  type CapacityRequest,
  type ChangeKind,
  type EnrolmentRow,
  type MaterialChange,
  type RosterRow,
  type Succession,
  type TransferRequest,
} from "@/api/delivery";
import { useAuth } from "@/auth/auth";
import { Button } from "@/components/ui/button";
import { DataTable, Note, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { ActionDialog, fmtDate, fmtDay, useCanManage, useIsManager } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";
import { useStaffOptions } from "@/features/shared/staff-picker";
import { timetableBody } from "./timetable";

const CLOSED = ["Completed", "Cancelled", "Archived"];
const MODES = ["Classroom", "Live Online", "Hybrid"].map((m) => ({ value: m, label: m }));
const opt = (values: string[]) => values.map((v) => ({ value: v, label: v }));
const blank = (label = "Not set") => ({ value: "", label });
const num = (v: string | undefined) => (v === undefined || v === "" ? null : Number(v));
const text = (v: string | undefined) => (v?.trim() ? v.trim() : null);

// ---------------------------------------------------------------- lifecycle

/** Propose, confirm / return, start, hold / resume, complete, cancel, archive: what each state and role may do. */
export function LifecycleActions({ batch }: { batch: BatchDetail }) {
  const { profile } = useAuth();
  const manager = useCanManage();
  const approver = useIsManager();
  const move = useDelivery(
    (v: { state: Parameters<typeof deliveryApi.batchState>[1]["state"]; reason?: string }) => deliveryApi.batchState(batch.batch_id, v),
    "Batch state updated",
  );
  const propose = useDelivery((note?: string) => deliveryApi.proposeBatch(batch.batch_id, note), "Proposed — confirm it when you are ready");
  const decide = useDelivery(
    (v: { decision: "Confirmed" | "Returned"; note?: string; override_reason?: string }) => deliveryApi.decideConfirmation(batch.batch_id, v),
    "Decision recorded",
  );
  const s = batch.state;
  const live = s === "Running" || s === "Full";
  const reason = { name: "reason", label: "Reason", type: "textarea" as const, required: true };
  const button = (label: string, variant: "default" | "outline" = "outline") => (
    <Button size="sm" variant={variant}>
      {label}
    </Button>
  );

  if (CLOSED.includes(s) && !(approver && (s === "Completed" || s === "Cancelled"))) return null;
  if (!manager) return null;
  return (
    <div className="mt-4 flex flex-wrap gap-2">
      {s === "Forming" && (
        <ActionDialog
          trigger={button("Propose batch", "default")}
          title={`Propose ${batch.batch_code}`}
          description="Proposes the batch for confirmation. The first six points of the readiness record must pass."
          fields={[{ name: "note", label: "Note", type: "textarea" }]}
          submitLabel="Propose"
          onSubmit={(v) => propose.mutateAsync(v["note"] || undefined)}
        />
      )}
      {s === "Proposed" && approver && (
        <>
          <ActionDialog
            trigger={button("Confirm batch", "default")}
            title={`Confirm ${batch.batch_code}`}
            description="Confirmed batches can take seats. If the checks raise warnings you will be asked why they are acceptable."
            fields={[
              { name: "note", label: "Note", type: "textarea" },
              { name: "override_reason", label: "Why the warnings are acceptable", type: "textarea", required: true, afterWarnings: true },
            ]}
            submitLabel="Confirm"
            onSubmit={(v) => decide.mutateAsync({ decision: "Confirmed", note: v["note"] || undefined, override_reason: v["override_reason"] || undefined })}
          />
          <ActionDialog
            trigger={button("Return to draft")}
            title={`Return ${batch.batch_code}`}
            description="The Branch Manager edits the batch and proposes it again."
            fields={[{ name: "note", label: "What needs to change", type: "textarea", required: true }]}
            submitLabel="Return"
            onSubmit={(v) => decide.mutateAsync({ decision: "Returned", note: v["note"] })}
          />
        </>
      )}
      {s === "Starting" && (
        <ActionDialog
          trigger={button("Start running", "default")}
          title={`Start ${batch.batch_code}`}
          description="The batch becomes In Progress."
          fields={[]}
          submitLabel="Start running"
          onSubmit={() => move.mutateAsync({ state: "Running" })}
        />
      )}
      {live && (
        <ActionDialog
          trigger={button("Complete batch", "default")}
          title={`Complete ${batch.batch_code}`}
          description="Needs: no open class, no replacement owed, no open disruption, no pending request, and a handover for every student still owed teaching."
          fields={[]}
          submitLabel="Complete batch"
          onSubmit={() => move.mutateAsync({ state: "Completed" })}
        />
      )}
      {approver && ["Proposed", "Starting", "Running", "Full"].includes(s) && (
        <ActionDialog
          trigger={button("Put on hold")}
          title={`Put ${batch.batch_code} on hold`}
          description="No new seats or requests until it is resumed."
          fields={[reason]}
          submitLabel="Put on hold"
          onSubmit={(v) => move.mutateAsync({ state: "On Hold", reason: v["reason"] })}
        />
      )}
      {approver && s === "On Hold" && (
        <ActionDialog
          trigger={button("Resume", "default")}
          title={`Resume ${batch.batch_code}`}
          description={batch.held_from_state ? `Goes back to ${batch.held_from_state}.` : undefined}
          fields={[{ name: "reason", label: "Note", type: "textarea" }]}
          submitLabel="Resume"
          onSubmit={(v) => move.mutateAsync({ state: "Resume", reason: v["reason"] || undefined })}
        />
      )}
      {["Forming", "Proposed", "Starting", "Running", "Full", "On Hold"].includes(s) && (
        <ActionDialog
          trigger={button("Cancel batch")}
          title={`Cancel ${batch.batch_code}`}
          description="Only possible once nobody holds a seat."
          fields={[reason]}
          submitLabel="Cancel batch"
          onSubmit={(v) => move.mutateAsync({ state: "Cancelled", reason: v["reason"] })}
        />
      )}
      {approver && (s === "Completed" || s === "Cancelled") && (
        <ActionDialog
          trigger={button("Archive batch")}
          title={`Archive ${batch.batch_code}`}
          description="Needs every seated student Completed or Withdrawn and no open recording issue."
          fields={[]}
          submitLabel="Archive"
          onSubmit={() => move.mutateAsync({ state: "Archived" })}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------- edit

export function EditBatchDialog({ batch }: { batch: BatchDetail }) {
  const update = useDelivery((body: Record<string, unknown>) => deliveryApi.updateBatch(batch.batch_id, body), "Batch updated");
  const current: Record<string, unknown> = {
    display_name: batch.display_name,
    batch_type: batch.batch_type,
    schedule_pattern: batch.schedule_pattern,
    capacity: batch.capacity,
    classroom_capacity: batch.classroom_capacity,
    lab_capacity: batch.lab_capacity,
    online_capacity: batch.online_capacity,
    mode: batch.mode,
    planned_start: batch.planned_start,
    planned_end: batch.planned_end,
    schedule_days: batch.schedule_days.length ? batch.schedule_days : null,
    start_time: batch.start_time,
    end_time: batch.end_time,
    location: batch.location,
    recording_provision: batch.recording_provision,
    recording_terms: batch.recording_terms,
    meet_series_link: batch.meet_series_link,
    meet_space_id: batch.meet_space_id,
    calendar_series_id: batch.calendar_series_id,
  };
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline">
          Edit batch
        </Button>
      }
      title={`Edit ${batch.batch_code}`}
      description="Only what you change is sent. Changing the start, mode, days, times or end of a confirmed batch with students is a material change: use the Requests tab."
      fields={[
        { name: "display_name", label: "Display name", value: batch.display_name ?? "" },
        { name: "batch_type", label: "Batch type", type: "select", options: opt(["Group", "Individual", "Corporate"]), value: batch.batch_type },
        { name: "schedule_pattern", label: "Schedule pattern", type: "select", options: opt(["Regular", "Weekend", "Fast-track"]), value: batch.schedule_pattern },
        { name: "capacity", label: "Capacity", type: "number", min: 1, required: true, value: String(batch.capacity), hint: "Raising it after Draft is a capacity request" },
        { name: "classroom_capacity", label: "Classroom capacity", type: "number", min: 0, value: batch.classroom_capacity?.toString() ?? "" },
        { name: "lab_capacity", label: "Lab capacity", type: "number", min: 0, value: batch.lab_capacity?.toString() ?? "" },
        { name: "online_capacity", label: "Online capacity", type: "number", min: 0, value: batch.online_capacity?.toString() ?? "" },
        { name: "mode", label: "Mode", type: "select", options: MODES, value: batch.mode },
        { name: "planned_start", label: "Planned start", type: "date", value: batch.planned_start ?? "" },
        { name: "planned_end", label: "Planned end", type: "date", value: batch.planned_end ?? "" },
        { name: "schedule_days", label: "Days", type: "days", value: batch.schedule_days.join(",") },
        { name: "start_time", label: "Start time (IST)", type: "time", value: batch.start_time ?? "" },
        { name: "end_time", label: "End time (IST)", type: "time", value: batch.end_time ?? "" },
        { name: "location", label: "Room", hint: "Classroom or lab; not used for Live Online", value: batch.location ?? "" },
        {
          name: "recording_provision",
          label: "Recording provision",
          type: "select",
          options: [blank(), ...opt(["Included", "Not Included", "Limited"])],
          value: batch.recording_provision ?? "",
        },
        { name: "recording_terms", label: "Recording terms", type: "textarea", value: batch.recording_terms ?? "" },
        { name: "meet_series_link", label: "Meet series link", value: batch.meet_series_link ?? "", placeholder: "https://meet.google.com/…" },
        { name: "meet_space_id", label: "Meet space ID", value: batch.meet_space_id ?? "" },
        { name: "calendar_series_id", label: "Calendar series ID", value: batch.calendar_series_id ?? "" },
      ]}
      onSubmit={(v) => {
        const next: Record<string, unknown> = {
          display_name: text(v["display_name"]),
          batch_type: v["batch_type"],
          schedule_pattern: v["schedule_pattern"],
          capacity: Number(v["capacity"]),
          classroom_capacity: num(v["classroom_capacity"]),
          lab_capacity: num(v["lab_capacity"]),
          online_capacity: num(v["online_capacity"]),
          mode: v["mode"],
          planned_start: v["planned_start"] || null,
          planned_end: v["planned_end"] || null,
          ...timetableBody(v),
          recording_provision: v["recording_provision"] || null,
          recording_terms: text(v["recording_terms"]),
          meet_series_link: text(v["meet_series_link"]),
          meet_space_id: text(v["meet_space_id"]),
          calendar_series_id: text(v["calendar_series_id"]),
        };
        const body = Object.fromEntries(Object.entries(next).filter(([k, x]) => JSON.stringify(x) !== JSON.stringify(current[k])));
        if (Object.keys(body).length === 0) return Promise.resolve();
        return update.mutateAsync(body);
      }}
    />
  );
}

// ---------------------------------------------------------------- transfers and handovers (roster row actions)

export function RequestTransferDialog({
  row,
  enrolment,
  targets,
}: {
  row: RosterRow;
  enrolment: EnrolmentRow | undefined;
  targets: Batch[];
}) {
  const request = useDelivery(
    (v: { enrolmentId: number; body: Parameters<typeof deliveryApi.requestTransfer>[1] }) => deliveryApi.requestTransfer(v.enrolmentId, v.body),
    "Transfer requested — the Branch Manager decides",
  );
  const tracks = enrolment?.tracks ?? [];
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline">
          Request transfer
        </Button>
      }
      title={`Request a transfer for ${row.student.full_name}`}
      description="The seat stays where it is until the request is approved. The current allocation is then kept as history."
      fields={[
        {
          name: "to_batch_id",
          label: "To batch",
          type: "select",
          required: true,
          options: targets.map((b) => ({ value: b.batch_id, label: `${b.display_name ?? b.batch_code} · ${b.batch_code} (${b.allocated_count}/${b.capacity}, ${b.state_label}) · ${b.branch.branch_name}` })),
        },
        ...(tracks.length > 0
          ? [
              {
                name: "enrolment_track_id",
                label: "Combo track",
                type: "select" as const,
                options: [blank("Whole enrolment"), ...tracks.map((t) => ({ value: t.enrolment_track_id, label: `${t.track_code} — ${t.track_name}` }))],
                value: row.enrolment_track_id ? String(row.enrolment_track_id) : "",
                hint: "A batch at another branch is allowed for one track only",
              },
            ]
          : []),
        { name: "reason", label: "Reason", type: "textarea" as const, required: true },
        { name: "ack", label: "Warnings", type: "checkbox" as const, hint: "I have reviewed the allocation warnings" },
      ]}
      submitLabel="Request transfer"
      onSubmit={(v) =>
        request.mutateAsync({
          enrolmentId: row.enrolment_id,
          body: {
            to_batch_id: Number(v["to_batch_id"]),
            enrolment_track_id: v["enrolment_track_id"] ? Number(v["enrolment_track_id"]) : null,
            reason: v["reason"]!,
            acknowledge_warnings: v["ack"] === "true",
          },
        })
      }
    />
  );
}

export function HandoverDialog({ batch, row, targets }: { batch: BatchDetail; row: RosterRow; targets: Batch[] }) {
  const owners = useStaffOptions(batch.branch.branch_id, ["BRANCH_MANAGER", "TRAINER"]);
  const record = useDelivery((body: Parameters<typeof deliveryApi.recordHandover>[1]) => deliveryApi.recordHandover(batch.batch_id, body), "Handover recorded");
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline">
          Handover
        </Button>
      }
      title={`Handover for ${row.student.full_name}`}
      description="For a student the batch still owes teaching (paused, not started). Needed before the batch can be completed."
      fields={[
        { name: "owner_user_id", label: "Owner", type: "select", required: true, options: owners },
        { name: "plan", label: "Plan", type: "textarea", required: true },
        { name: "destination", label: "Where the student goes", required: true, placeholder: "A later batch, a remedial plan…" },
        {
          name: "destination_batch_id",
          label: "Destination batch",
          type: "select",
          options: [blank("None yet"), ...targets.map((b) => ({ value: b.batch_id, label: `${b.batch_code} (${b.state_label})` }))],
          value: "",
        },
      ]}
      submitLabel="Record handover"
      onSubmit={(v) =>
        record.mutateAsync({
          enrolment_id: row.enrolment_id,
          owner_user_id: Number(v["owner_user_id"]),
          plan: v["plan"]!,
          destination: v["destination"]!,
          destination_batch_id: v["destination_batch_id"] ? Number(v["destination_batch_id"]) : null,
        })
      }
    />
  );
}

// ---------------------------------------------------------------- requests tab

const who = (u: { full_name: string } | null) => u?.full_name ?? "—";

function DecisionButtons({
  onApprove,
  onReject,
  what,
  approveLabel = "Approve",
}: {
  onApprove: () => Promise<unknown> | unknown;
  onReject: (note: string) => Promise<unknown>;
  what: string;
  approveLabel?: string;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <Button size="sm" onClick={() => void onApprove()}>
        {approveLabel}
      </Button>
      <ActionDialog
        trigger={
          <Button size="sm" variant="outline">
            Reject
          </Button>
        }
        title={`Reject the ${what}`}
        fields={[{ name: "note", label: "Why", type: "textarea", required: true }]}
        submitLabel="Reject"
        onSubmit={(v) => onReject(v["note"]!)}
      />
    </div>
  );
}

function CapacityRequests({ batch, manager, approver }: { batch: BatchDetail; manager: boolean; approver: boolean }) {
  const query = useQuery({ queryKey: ["delivery", "capacity-requests", batch.batch_id], queryFn: () => deliveryApi.capacityRequests({ batch_id: batch.batch_id }) });
  const request = useDelivery((body: Record<string, unknown>) => deliveryApi.requestCapacity(batch.batch_id, body), "Capacity request sent");
  const decide = useDelivery(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => deliveryApi.decideCapacity(v.id, { decision: v.decision, note: v.note }),
    "Decision recorded",
  );
  const cols = [
    { h: "Change", c: (r: CapacityRequest) => `${r.from_capacity} → ${r.to_capacity} seats` },
    {
      h: "Sides",
      c: (r: CapacityRequest) =>
        [r.classroom_capacity != null && `classroom ${r.classroom_capacity}`, r.lab_capacity != null && `lab ${r.lab_capacity}`, r.online_capacity != null && `online ${r.online_capacity}`]
          .filter(Boolean)
          .join(" · ") || "—",
    },
    {
      h: "Evidence",
      c: (r: CapacityRequest) => (
        <>
          <div>
            <span className="text-muted-foreground">Resources: </span>
            {r.resource_validation}
          </div>
          <div>
            <span className="text-muted-foreground">Academic review: </span>
            {r.academic_review}
          </div>
        </>
      ),
    },
    {
      h: "Status",
      c: (r: CapacityRequest) => (
        <>
          <StatusBadge domain="approval" code={r.status} />
          <div className="mt-1 text-xs text-muted-foreground">
            {who(r.requested_by)}, {fmtDate(r.requested_at)}
            {r.decision_note ? ` · ${r.decision_note}` : ""}
          </div>
        </>
      ),
    },
    ...(approver
      ? [
          {
            h: "Decision",
            c: (r: CapacityRequest) =>
              r.status === "Pending" ? (
                <DecisionButtons
                  what="capacity request"
                  onApprove={() => decide.mutate({ id: r.request_id, decision: "Approved" })}
                  onReject={(note) => decide.mutateAsync({ id: r.request_id, decision: "Rejected", note })}
                />
              ) : (
                "—"
              ),
          },
        ]
      : []),
  ];
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Capacity requests</h3>
        {manager && !CLOSED.includes(batch.state) && (
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Request capacity increase
              </Button>
            }
            title={`Increase the capacity of ${batch.batch_code}`}
            description={`Now ${batch.capacity} seats. Seats never exceed the verified side of the mode. One request can be open at a time.`}
            fields={[
              { name: "to_capacity", label: "New capacity", type: "number", min: batch.capacity + 1, required: true, value: String(batch.capacity + 1) },
              { name: "classroom_capacity", label: "Classroom capacity", type: "number", min: 0, value: batch.classroom_capacity?.toString() ?? "" },
              { name: "lab_capacity", label: "Lab capacity", type: "number", min: 0, value: batch.lab_capacity?.toString() ?? "" },
              { name: "online_capacity", label: "Online capacity", type: "number", min: 0, value: batch.online_capacity?.toString() ?? "" },
              { name: "resource_validation", label: "Resource validation", type: "textarea", required: true, hint: "Rooms, seats, devices or licences checked" },
              { name: "academic_review", label: "Academic review", type: "textarea", required: true, hint: "Why the larger group still works academically" },
            ]}
            submitLabel="Send request"
            onSubmit={(v) =>
              request.mutateAsync({
                to_capacity: Number(v["to_capacity"]),
                classroom_capacity: num(v["classroom_capacity"]),
                lab_capacity: num(v["lab_capacity"]),
                online_capacity: num(v["online_capacity"]),
                resource_validation: v["resource_validation"],
                academic_review: v["academic_review"],
              })
            }
          />
        )}
      </div>
      <QueryView query={query}>
        {(page) => <DataTable caption="Capacity requests" rows={page.data} getKey={(r) => r.request_id} cols={cols} empty="No capacity requests for this batch." />}
      </QueryView>
    </div>
  );
}

function TransferRequests({ batch, manager, approver }: { batch: BatchDetail; manager: boolean; approver: boolean }) {
  const query = useQuery({ queryKey: ["delivery", "transfer-requests", batch.batch_id], queryFn: () => deliveryApi.transferRequests({ batch_id: batch.batch_id }) });
  const destination = useDelivery(
    (v: { id: number; decision: "Confirmed" | "Rejected"; note?: string }) => deliveryApi.confirmDestination(v.id, { decision: v.decision, note: v.note }),
    "Destination answer recorded",
  );
  const decide = useDelivery(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => deliveryApi.decideTransfer(v.id, { decision: v.decision, note: v.note }),
    "Transfer decision recorded",
  );
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">Transfer requests</h3>
      <QueryView query={query}>
        {(page) => (
          <DataTable
            caption="Transfer requests"
            rows={page.data}
            getKey={(r) => r.request_id}
            empty="No transfer requests for this batch."
            cols={[
              { h: "Student", c: (r: TransferRequest) => r.enrolment?.enrolment_code ?? `Enrolment ${r.enrolment_id}` },
              {
                h: "Move",
                c: (r: TransferRequest) => (
                  <>
                    {r.from_batch?.batch_code ?? "—"} → {r.to_batch.batch_code}
                    {r.enrolment_track_id && <div className="text-xs text-muted-foreground">One combo track</div>}
                    {r.interbranch && <Tag tone="info">Another branch</Tag>}
                  </>
                ),
              },
              { h: "Reason", c: (r: TransferRequest) => r.reason },
              {
                h: "Status",
                c: (r: TransferRequest) => (
                  <>
                    <StatusBadge domain="approval" code={r.status} />
                    <div className="mt-1 text-xs text-muted-foreground">
                      {who(r.requested_by)}, {fmtDate(r.requested_at)}
                      {r.decision_note ? ` · ${r.decision_note}` : ""}
                    </div>
                    {r.interbranch && (
                      <div className="mt-1 text-xs text-muted-foreground">
                        {r.destination_confirmed_at ? `Destination confirmed by ${who(r.destination_confirmed_by)}` : "Destination has not confirmed delivery"}
                      </div>
                    )}
                  </>
                ),
              },
              ...(manager
                ? [
                    {
                      h: "Actions",
                      c: (r: TransferRequest) => {
                        if (r.status !== "Pending") return "—";
                        const atDestination = r.interbranch && r.to_branch_id === batch.branch.branch_id && !r.destination_confirmed_at;
                        return (
                          <div className="space-y-1.5">
                            {atDestination && (
                              <div className="flex flex-wrap gap-1.5">
                                <Button size="sm" variant="outline" onClick={() => destination.mutate({ id: r.request_id, decision: "Confirmed" })}>
                                  Confirm delivery
                                </Button>
                                <ActionDialog
                                  trigger={
                                    <Button size="sm" variant="ghost">
                                      Cannot deliver
                                    </Button>
                                  }
                                  title="We cannot deliver this track"
                                  fields={[{ name: "note", label: "Why", type: "textarea", required: true }]}
                                  submitLabel="Send"
                                  onSubmit={(v) => destination.mutateAsync({ id: r.request_id, decision: "Rejected", note: v["note"] })}
                                />
                              </div>
                            )}
                            {approver && (
                              <DecisionButtons
                                what="transfer"
                                onApprove={() => decide.mutate({ id: r.request_id, decision: "Approved" })}
                                onReject={(note) => decide.mutateAsync({ id: r.request_id, decision: "Rejected", note })}
                              />
                            )}
                          </div>
                        );
                      },
                    },
                  ]
                : []),
            ]}
          />
        )}
      </QueryView>
    </div>
  );
}

function countsLabel(counts: Record<string, number>) {
  const parts = Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${n} ${k.toLowerCase()}`);
  return parts.length ? parts.join(" · ") : "No students";
}

const CHANGE_FIELD_NAMES = ["planned_start", "planned_end", "mode", "schedule_days", "start_time", "end_time", "target_batch_id"];

function describeChanges(changes: Record<string, unknown> | null) {
  const entries = Object.entries(changes ?? {}).filter(([, v]) => v !== null && v !== undefined && v !== "");
  return entries.length ? entries.map(([k, v]) => `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.join(", ") : String(v)}`).join(" · ") : null;
}

function MaterialChanges({ batch, manager, approver, roster, sameCourse }: { batch: BatchDetail; manager: boolean; approver: boolean; roster: RosterRow[]; sameCourse: Batch[] }) {
  const query = useQuery({ queryKey: ["delivery", "material-changes", batch.batch_id], queryFn: () => deliveryApi.changes({ batch_id: batch.batch_id }) });
  const propose = useDelivery((body: Record<string, unknown>) => deliveryApi.proposeChange(batch.batch_id, body), "Material change proposed — the Branch Manager decides");
  const decide = useDelivery(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => deliveryApi.decideChange(v.id, { decision: v.decision, note: v.note }),
    "Decision recorded",
  );
  const apply = useDelivery((id: number) => deliveryApi.applyChange(id), "Change applied");
  const withdraw = useDelivery((v: { id: number; note: string }) => deliveryApi.withdrawChange(v.id, v.note), "Change withdrawn");
  const names = new Map(roster.map((r) => [r.enrolment_id, `${r.student.full_name} (${r.enrolment.enrolment_code})`]));
  const is = (kind: ChangeKind) => (v: Record<string, string>) => v["kind"] === kind;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Material changes</h3>
        {manager && !CLOSED.includes(batch.state) && (
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Propose a material change
              </Button>
            }
            title={`Material change to ${batch.batch_code}`}
            description="Start, mode, teaching days and times, and an end extension affect students already seated. Each student is asked to agree after the Branch Manager approves."
            fields={[
              { name: "kind", label: "What changes", type: "select", options: opt([...CHANGE_KINDS]), required: true },
              { name: "planned_start", label: "New start date", type: "date", required: true, showIf: is("Start date") },
              { name: "mode", label: "New delivery mode", type: "select", options: MODES, required: true, showIf: is("Delivery mode"), value: batch.mode },
              { name: "schedule_days", label: "New teaching days", type: "days", showIf: is("Teaching days / times"), value: batch.schedule_days.join(",") },
              { name: "start_time", label: "New start time (IST)", type: "time", showIf: is("Teaching days / times"), value: batch.start_time ?? "" },
              { name: "end_time", label: "New end time (IST)", type: "time", showIf: is("Teaching days / times"), value: batch.end_time ?? "" },
              { name: "planned_end", label: "New end date", type: "date", required: true, showIf: is("End date extension") },
              {
                name: "target_batch_id",
                label: "Move students to",
                type: "select",
                required: true,
                showIf: is("Batch move"),
                options: sameCourse.filter((b) => b.batch_id !== batch.batch_id).map((b) => ({ value: b.batch_id, label: `${b.batch_code} (${b.state_label})` })),
              },
              { name: "proposed_plan", label: "Proposed plan", type: "textarea", required: true },
              { name: "reason", label: "Reason", type: "textarea", required: true },
              { name: "alternative", label: "Alternative for a student who says no", type: "textarea" },
            ]}
            submitLabel="Propose change"
            onSubmit={(v) => {
              const changes: Record<string, unknown> = {};
              for (const key of CHANGE_FIELD_NAMES) {
                const value = v[key];
                if (!value) continue;
                changes[key] = key === "schedule_days" ? value.split(",") : key === "target_batch_id" ? Number(value) : value;
              }
              return propose.mutateAsync({
                kind: v["kind"],
                proposed_plan: v["proposed_plan"],
                reason: v["reason"],
                alternative: v["alternative"] || undefined,
                changes: Object.keys(changes).length ? changes : undefined,
              });
            }}
          />
        )}
      </div>
      <QueryView query={query}>
        {(page) => (
          <DataTable
            caption="Material changes"
            rows={page.data}
            getKey={(c) => c.change_id}
            empty="No material changes for this batch."
            cols={[
              {
                h: "Change",
                c: (c: MaterialChange) => (
                  <>
                    <div className="font-medium">{c.kind}</div>
                    <div>{c.proposed_plan}</div>
                    {describeChanges(c.changes) && <div className="text-xs text-muted-foreground">{describeChanges(c.changes)}</div>}
                    <div className="text-xs text-muted-foreground">Reason: {c.reason}</div>
                    {c.alternative && <div className="text-xs text-muted-foreground">Alternative: {c.alternative}</div>}
                  </>
                ),
              },
              {
                h: "Status",
                c: (c: MaterialChange) => (
                  <>
                    <StatusBadge domain="approval" code={c.status} />
                    <div className="mt-1 text-xs text-muted-foreground">
                      {who(c.requested_by)}, {fmtDate(c.requested_at)}
                      {c.decision_note ? ` · ${c.decision_note}` : ""}
                    </div>
                  </>
                ),
              },
              { h: "Students' answers", c: (c: MaterialChange) => countsLabel(c.response_counts) },
              ...(manager
                ? [
                    {
                      h: "Actions",
                      c: (c: MaterialChange) => (
                        <div className="space-y-1.5">
                          {approver && c.status === "Pending Approval" && (
                            <DecisionButtons
                              what="material change"
                              onApprove={() => decide.mutate({ id: c.change_id, decision: "Approved" })}
                              onReject={(note) => decide.mutateAsync({ id: c.change_id, decision: "Rejected", note })}
                            />
                          )}
                          {c.status === "Awaiting Agreement" && (
                            <div className="flex flex-wrap gap-1.5">
                              <RecordAnswerDialog change={c} names={names} />
                              <Button size="sm" onClick={() => apply.mutate(c.change_id)}>
                                Apply
                              </Button>
                            </div>
                          )}
                          {(c.status === "Pending Approval" || c.status === "Awaiting Agreement") && (
                            <ActionDialog
                              trigger={
                                <Button size="sm" variant="ghost">
                                  Withdraw
                                </Button>
                              }
                              title="Withdraw the material change"
                              fields={[{ name: "note", label: "Why", type: "textarea", required: true }]}
                              submitLabel="Withdraw"
                              onSubmit={(v) => withdraw.mutateAsync({ id: c.change_id, note: v["note"]! })}
                            />
                          )}
                          {c.status !== "Pending Approval" && c.status !== "Awaiting Agreement" && "—"}
                        </div>
                      ),
                    },
                  ]
                : []),
            ]}
          />
        )}
      </QueryView>
    </div>
  );
}

/** A student's answer given outside the LMS (in person, by phone), recorded with its evidence. */
function RecordAnswerDialog({ change, names }: { change: MaterialChange; names: Map<number, string> }) {
  const detail = useQuery({ queryKey: ["delivery", "material-change", change.change_id], queryFn: () => deliveryApi.change(change.change_id) });
  const record = useDelivery((body: Parameters<typeof deliveryApi.recordChangeResponse>[1]) => deliveryApi.recordChangeResponse(change.change_id, body), "Answer recorded");
  const pending = (detail.data?.responses ?? []).filter((r) => r.response === "Pending");
  return (
    <ActionDialog
      trigger={
        <Button size="sm" variant="outline" disabled={detail.isPending}>
          Record answer
        </Button>
      }
      title="Record a student's answer"
      description="For an answer given outside the LMS. Keep the evidence note specific. A decline needs the alternative that was arranged."
      fields={[
        {
          name: "enrolment_id",
          label: "Student",
          type: "select",
          required: true,
          options: pending.map((r) => ({ value: r.enrolment_id, label: names.get(r.enrolment_id) ?? `Enrolment ${r.enrolment_id}` })),
        },
        { name: "response", label: "Answer", type: "select", options: opt(["Agreed", "Declined"]), value: "Agreed" },
        { name: "note", label: "Evidence note", type: "textarea", required: true, hint: "How and when the student answered" },
        { name: "alternative_arranged", label: "Alternative arranged", type: "textarea", required: true, showIf: (v) => v["response"] === "Declined" },
      ]}
      submitLabel="Record answer"
      onSubmit={(v) =>
        record.mutateAsync({
          enrolment_id: Number(v["enrolment_id"]),
          response: v["response"] as "Agreed" | "Declined",
          note: v["note"]!,
          alternative_arranged: v["alternative_arranged"] || undefined,
        })
      }
    />
  );
}

function Successions({ batch, manager, approver, roster, sameCourse }: { batch: BatchDetail; manager: boolean; approver: boolean; roster: RosterRow[]; sameCourse: Batch[] }) {
  const request = useDelivery((body: Record<string, unknown>) => deliveryApi.requestSuccession(body), "Request sent — the Branch Manager decides");
  const decide = useDelivery(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => deliveryApi.decideSuccession(v.id, { decision: v.decision, note: v.note }),
    "Decision recorded",
  );
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Merge and split</h3>
        {manager && !CLOSED.includes(batch.state) && (
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Request merge or split
              </Button>
            }
            title={`Merge or split ${batch.batch_code}`}
            description="Merge moves every student of this batch into the other batch. Split moves the students you choose. Same branch, course or track and curriculum version; a different mode or timetable needs an applied Batch move material change first."
            fields={[
              { name: "kind", label: "What to do", type: "select", options: [{ value: "Merge", label: "Merge into another batch" }, { value: "Split", label: "Split students out to another batch" }] },
              {
                name: "to_batch_id",
                label: "Other batch",
                type: "select",
                required: true,
                options: sameCourse.filter((b) => b.batch_id !== batch.batch_id).map((b) => ({ value: b.batch_id, label: `${b.batch_code} (${b.allocated_count}/${b.capacity}, ${b.state_label})` })),
              },
              {
                name: "enrolment_ids",
                label: "Students to move",
                type: "multiselect",
                required: true,
                showIf: (v) => v["kind"] === "Split",
                options: roster.filter((r) => r.status === "Active").map((r) => ({ value: r.enrolment_id, label: `${r.student.full_name} (${r.enrolment.enrolment_code})` })),
              },
              { name: "effective_from", label: "Effective from", type: "date", required: true },
              { name: "reason", label: "Reason", type: "textarea", required: true },
              { name: "academic_review", label: "Academic review", type: "textarea", required: true, hint: "Why the students' learning is not harmed" },
            ]}
            submitLabel="Send request"
            onSubmit={(v) =>
              request.mutateAsync({
                kind: v["kind"],
                from_batch_id: batch.batch_id,
                to_batch_id: Number(v["to_batch_id"]),
                enrolment_ids: v["kind"] === "Split" ? (v["enrolment_ids"] ?? "").split(",").filter(Boolean).map(Number) : undefined,
                effective_from: v["effective_from"],
                reason: v["reason"],
                academic_review: v["academic_review"],
              })
            }
          />
        )}
      </div>
      <DataTable
        caption="Merge and split requests"
        rows={batch.successions}
        getKey={(s) => s.succession_id}
        empty="No merge or split requests for this batch."
        cols={[
          { h: "Request", c: (s: Succession) => `${s.kind}: ${s.from_batch.batch_code} → ${s.to_batch.batch_code}` },
          { h: "From", c: (s: Succession) => fmtDay(s.effective_from) },
          {
            h: "Why",
            c: (s: Succession) => (
              <>
                <div>{s.reason}</div>
                <div className="text-xs text-muted-foreground">Academic review: {s.academic_review}</div>
                {s.enrolment_ids && <div className="text-xs text-muted-foreground">{s.enrolment_ids.length} student(s)</div>}
              </>
            ),
          },
          {
            h: "Status",
            c: (s: Succession) => (
              <>
                <StatusBadge domain="approval" code={s.status} />
                <div className="mt-1 text-xs text-muted-foreground">
                  {who(s.requested_by)}, {fmtDate(s.requested_at)}
                  {s.status === "Approved" && s.moved_count != null ? ` · ${s.moved_count} moved` : ""}
                  {s.decision_note ? ` · ${s.decision_note}` : ""}
                </div>
              </>
            ),
          },
          ...(approver
            ? [
                {
                  h: "Decision",
                  c: (s: Succession) =>
                    s.status === "Pending" ? (
                      <DecisionButtons
                        what="request"
                        onApprove={() => decide.mutate({ id: s.succession_id, decision: "Approved" })}
                        onReject={(note) => decide.mutateAsync({ id: s.succession_id, decision: "Rejected", note })}
                      />
                    ) : (
                      "—"
                    ),
                },
              ]
            : []),
        ]}
      />
    </div>
  );
}

export function RequestsTab({ batch }: { batch: BatchDetail }) {
  const manager = useCanManage();
  const approver = useIsManager();
  const roster = useQuery({ queryKey: ["delivery", "roster", batch.batch_id, false], queryFn: () => deliveryApi.roster(batch.batch_id, { status: "Active" }) });
  const sameCourse = useQuery({
    queryKey: ["delivery", "batches", "same-course", batch.course.course_id, batch.branch.branch_id],
    queryFn: () => deliveryApi.batches({ course_id: batch.course.course_id, branch_id: batch.branch.branch_id }),
    enabled: manager,
  });
  const rows = roster.data?.data ?? [];
  const targets = (sameCourse.data?.data ?? []).filter((b) => !CLOSED.includes(b.state));
  return (
    <div className="space-y-6">
      <CapacityRequests batch={batch} manager={manager} approver={approver} />
      <TransferRequests batch={batch} manager={manager} approver={approver} />
      <MaterialChanges batch={batch} manager={manager} approver={approver} roster={rows} sameCourse={targets} />
      <Successions batch={batch} manager={manager} approver={approver} roster={rows} sameCourse={targets} />
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Completion handovers</h3>
        <DataTable
          caption="Handovers"
          rows={batch.handovers}
          getKey={(h) => h.handover_id}
          empty="No handovers recorded."
          cols={[
            { h: "Student", c: (h) => rows.find((r) => r.enrolment_id === h.enrolment_id)?.student.full_name ?? `Enrolment ${h.enrolment_id}` },
            { h: "Owner", c: (h) => who(h.owner) },
            { h: "Plan", c: (h) => h.plan },
            { h: "Goes to", c: (h) => h.destination },
            { h: "Recorded", c: (h) => fmtDate(h.recorded_at) },
          ]}
        />
        <Note>Record a handover from the Students tab, for a student the batch still owes teaching.</Note>
      </div>
    </div>
  );
}
