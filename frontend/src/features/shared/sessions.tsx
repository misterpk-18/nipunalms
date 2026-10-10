/** Class-session tables and actions shared by the trainer, academic and branch workspaces, plus the batch roster. */
import { useQuery } from "@tanstack/react-query";
import { deliveryApi, type Batch, type ClassLog, type ClassSession, type RescheduleRequest } from "@/api/delivery";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { DataTable, QueryView, StatusBadge, Tag, type Column } from "@/components/lms/ui";
import { useAuth } from "@/auth/auth";
import { useApiMutation } from "@/lib/mutation";
import { ActionDialog, MeetBadge, StateBadge, fmtDay, fmtRange, fromIstInput, mono, toIstInput, useIsManager } from "./delivery-ui";

/** A mutation that refreshes every delivery query afterwards. */
export function useDelivery<TVars, TResult>(fn: (vars: TVars) => Promise<TResult>, success: string) {
  return useApiMutation(fn, { success, invalidate: [["delivery"]] });
}

const START_OPENS_MS = 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;
const OUTCOMES = [
  { value: "Held", label: "Held in full" },
  { value: "Partially Held", label: "Partially held" },
];

export function SessionActions({ session, manager, trainer: isTrainer }: { session: ClassSession; manager: boolean; trainer: boolean }) {
  const { profile } = useAuth();
  const approver = useIsManager();
  const trainer = isTrainer && session.trainer.user_id === profile?.user.user_id; // only the trainer who teaches it
  const start = useDelivery((id: number) => deliveryApi.startSession(id), "Class started");
  const deliver = useDelivery((v: { id: number; log: ClassLog }) => deliveryApi.deliverSession(v.id, v.log), "Marked as delivered");
  const reschedule = useDelivery(
    (v: { id: number; body: Parameters<typeof deliveryApi.reschedule>[1] }) => deliveryApi.reschedule(v.id, v.body),
    "Session rescheduled — the batch has been told",
  );
  const cancel = useDelivery(
    (v: { id: number; body: Parameters<typeof deliveryApi.cancelSession>[1] }) => deliveryApi.cancelSession(v.id, v.body),
    "Session cancelled — the batch has been told",
  );
  const request = useDelivery(
    (v: { id: number; starts_at: string; ends_at: string; reason: string }) =>
      deliveryApi.requestReschedule(v.id, { proposed_starts_at: v.starts_at, proposed_ends_at: v.ends_at, reason: v.reason }),
    "Reschedule requested",
  );
  const confirm = useDelivery((id: number) => deliveryApi.confirmSession(id), "Class confirmed");
  const decide = useDelivery(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => deliveryApi.decidePurpose(v.id, { decision: v.decision, note: v.note }),
    "Decision recorded",
  );
  const waive = useDelivery((v: { id: number; reason: string }) => deliveryApi.waiveReplacement(v.id, v.reason), "Recorded: no replacement needed");
  const link = useDelivery((v: { id: number; link: string }) => deliveryApi.meetLink(v.id, v.link), "Meet link recorded");
  const failed = useDelivery((v: { id: number; detail: string }) => deliveryApi.meetFailed(v.id, v.detail), "Meet association marked as failed");
  const reset = useDelivery((id: number) => deliveryApi.meetReset(id), "Meet association reset");

  const open = session.state === "Scheduled" || session.state === "Rescheduled";
  const awaitingApproval = session.approval_status === "Pending";
  const started = Date.now() >= new Date(session.starts_at).getTime();
  const canStart = (manager || trainer) && open && !awaitingApproval && Date.now() >= new Date(session.starts_at).getTime() - START_OPENS_MS;
  const canDeliver = (manager || trainer) && (session.state === "Live" || (open && started && !awaitingApproval));
  const online = session.mode !== "Classroom";
  const within24 = new Date(session.starts_at).getTime() - Date.now() < DAY_MS;
  const times = [
    { name: "starts_at", label: "New start (IST)", type: "datetime" as const, required: true, value: toIstInput(session.starts_at) },
    { name: "ends_at", label: "New end (IST)", type: "datetime" as const, required: true, value: toIstInput(session.ends_at) },
  ];
  const reasonField = { name: "reason", label: "Reason", type: "textarea" as const, required: true };
  const emergencyFields = [
    {
      name: "emergency_reason",
      label: "Emergency reason",
      type: "textarea" as const,
      required: within24,
      hint: within24 ? "The class starts within 24 hours, so this is needed" : "Only needed when the class starts within 24 hours",
    },
    {
      name: "next_action",
      label: "Next action",
      type: "textarea" as const,
      required: within24,
      hint: within24 ? "What happens next for the students" : "Only needed when the class starts within 24 hours",
    },
  ];
  const overrideField = { name: "override_reason", label: "Reason to override the warning", type: "textarea" as const, required: true, afterWarnings: true };
  const emergency = (v: Record<string, string>) => ({ emergency_reason: v["emergency_reason"] || undefined, next_action: v["next_action"] || undefined });

  return (
    <div className="flex flex-wrap gap-1.5">
      {canStart && open && (
        <Button size="sm" onClick={() => start.mutate(session.session_id)}>
          Start
        </Button>
      )}
      {manager && open && !session.confirmed_at && !awaitingApproval && (
        <Button size="sm" variant="outline" onClick={() => confirm.mutate(session.session_id)}>
          Confirm
        </Button>
      )}
      {approver && awaitingApproval && open && (
        <>
          <Button size="sm" onClick={() => decide.mutate({ id: session.session_id, decision: "Approved" })}>
            Approve {session.purpose.toLowerCase()} class
          </Button>
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Reject
              </Button>
            }
            title={`Reject the ${session.purpose.toLowerCase()} class`}
            description="Students never see a rejected class and it owes nothing."
            fields={[{ name: "note", label: "Note", type: "textarea" }]}
            submitLabel="Reject"
            onSubmit={(v) => decide.mutateAsync({ id: session.session_id, decision: "Rejected", note: v["note"] || undefined })}
          />
        </>
      )}
      {canDeliver && (
        <ActionDialog
          trigger={
            <Button size="sm" variant="outline">
              Mark delivered
            </Button>
          }
          title={`Class log: "${session.title}"`}
          description="The class log: record what actually happened. Attendance is marked separately."
          fields={[
            { name: "outcome", label: "Outcome", type: "select", options: OUTCOMES, value: "Held" },
            // Closing a class early: the end defaults to now, never a time still in the future
            // Defaults: from when the trainer started the class to its scheduled end, or to now when it closes early
            { name: "actual_start", label: "Actual start (IST)", type: "datetime", value: toIstInput(session.live_at ?? session.starts_at) },
            { name: "actual_end", label: "Actual end (IST)", type: "datetime", value: toIstInput(logEnd(session.live_at ?? session.starts_at, session.ends_at)) },
            { name: "break_minutes", label: "Break minutes", type: "number", min: 0, value: "0" },
            {
              name: "unfulfilled_note",
              label: "What was not delivered",
              type: "textarea",
              required: true,
              showIf: (v) => v["outcome"] === "Partially Held",
            },
            { name: "notes", label: "Notes (topics covered)", type: "textarea" },
          ]}
          submitLabel="Mark delivered"
          onSubmit={(v) =>
            deliver.mutateAsync({
              id: session.session_id,
              log: {
                outcome: v["outcome"] as "Held" | "Partially Held",
                actual_start: v["actual_start"] ? fromIstInput(v["actual_start"]) : undefined,
                actual_end: v["actual_end"] ? fromIstInput(v["actual_end"]) : undefined,
                break_minutes: v["break_minutes"] ? Number(v["break_minutes"]) : undefined,
                unfulfilled_note: v["unfulfilled_note"] || undefined,
                notes: v["notes"] || undefined,
              },
            })
          }
        />
      )}
      {manager && open && (
        <>
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Reschedule
              </Button>
            }
            title={`Reschedule "${session.title}"`}
            description="The batch's students and the trainer are notified; the original slot is kept in the history. A booked room or a student clash is a warning only a Branch Manager can override."
            fields={[...times, reasonField, ...emergencyFields, ...(approver ? [overrideField] : [])]}
            submitLabel="Reschedule"
            onSubmit={(v) =>
              reschedule.mutateAsync({
                id: session.session_id,
                body: {
                  starts_at: fromIstInput(v["starts_at"]!),
                  ends_at: fromIstInput(v["ends_at"]!),
                  reason: v["reason"]!,
                  override_reason: v["override_reason"] || undefined,
                  ...emergency(v),
                },
              })
            }
          />
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Cancel
              </Button>
            }
            title={`Cancel "${session.title}"`}
            description="A cancelled class is not a student absence. It owes a replacement unless you record that none is needed."
            fields={[reasonField, ...emergencyFields]}
            submitLabel="Cancel session"
            onSubmit={(v) => cancel.mutateAsync({ id: session.session_id, body: { reason: v["reason"]!, ...emergency(v) } })}
          />
        </>
      )}
      {manager && session.state === "Cancelled" && !session.replacement_waiver && session.approval_status !== "Rejected" && (
        <ActionDialog
          trigger={
            <Button size="sm" variant="outline">
              No replacement needed
            </Button>
          }
          title="No replacement needed"
          description="This stops the cancelled class from being listed as owing a replacement."
          fields={[reasonField]}
          submitLabel="Record"
          onSubmit={(v) => waive.mutateAsync({ id: session.session_id, reason: v["reason"]! })}
        />
      )}
      {trainer && !manager && open && !session.open_request_id && (
        <ActionDialog
          trigger={
            <Button size="sm" variant="outline">
              Request reschedule
            </Button>
          }
          title={`Request to move "${session.title}"`}
          description="Your Branch Manager decides."
          fields={[
            { name: "starts_at", label: "Proposed start (IST)", type: "datetime", required: true, value: toIstInput(session.starts_at) },
            { name: "ends_at", label: "Proposed end (IST)", type: "datetime", required: true, value: toIstInput(session.ends_at) },
            reasonField,
          ]}
          submitLabel="Send request"
          onSubmit={(v) =>
            request.mutateAsync({
              id: session.session_id,
              starts_at: fromIstInput(v["starts_at"]!),
              ends_at: fromIstInput(v["ends_at"]!),
              reason: v["reason"]!,
            })
          }
        />
      )}
      {trainer && !manager && session.open_request_id && <StatusBadge domain="approval" code="Requested" label="Reschedule requested" />}
      {manager && open && online && (
        <>
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Meet link
              </Button>
            }
            title="Record the Meet link"
            description={`Organizer: ${session.organizer_email ?? "branch mailbox"}. The LMS records the link; it never calls Google. A link used by another batch's open class is refused.`}
            fields={[{ name: "link", label: "Meet link", required: true, placeholder: "https://meet.google.com/abc-defg-hij" }]}
            submitLabel="Save link"
            onSubmit={(v) => link.mutateAsync({ id: session.session_id, link: v["link"]! })}
          />
          <ActionDialog
            trigger={
              <Button size="sm" variant="ghost">
                Meet failed
              </Button>
            }
            title="Mark the Meet association as failed"
            description="The branch's Branch Managers and manager get a recovery task."
            fields={[{ name: "detail", label: "What went wrong", type: "textarea", required: true }]}
            submitLabel="Mark failed"
            onSubmit={(v) => failed.mutateAsync({ id: session.session_id, detail: v["detail"]! })}
          />
          {(session.meet_status === "Linked" || session.meet_status === "Unavailable") && (
            <Button size="sm" variant="ghost" onClick={() => reset.mutate(session.session_id)}>
              {session.meet_status === "Linked" ? "Remove link" : "Retry"}
            </Button>
          )}
        </>
      )}
    </div>
  );
}

export function sessionColumns(actions: { manager: boolean; trainer: boolean } | null, withBranch = false): Column<ClassSession>[] {
  const cols: Column<ClassSession>[] = [
    { h: "When (IST)", c: (s) => fmtRange(s.starts_at, s.ends_at) },
    {
      h: "Session",
      c: (s) => (
        <>
          <div className="font-medium">{s.title}</div>
          <div className="text-xs text-muted-foreground">
            {s.session_code} · {s.mode}
            {s.room ? ` · ${s.room}` : ""}
            {s.topic ? ` · ${s.topic.title}` : ""}
          </div>
          {(s.purpose !== "Regular" || s.approval_status === "Pending") && (
            <div className="mt-1 flex flex-wrap gap-1">
              {s.purpose !== "Regular" && <Tag tone="info">{s.purpose} class</Tag>}
              {s.approval_status === "Pending" && <StatusBadge domain="approval" code="Pending" label="Awaiting approval" />}
              {s.approval_status === "Rejected" && <StatusBadge domain="approval" code="Rejected" label="Not approved" />}
            </div>
          )}
          {s.state === "Cancelled" && s.replacement_waiver && <div className="mt-1 text-xs text-muted-foreground">No replacement needed: {s.replacement_waiver}</div>}
          {s.delivered_minutes != null && s.planned_minutes != null && (s.state === "Delivered" || s.state === "Live") && (
            <div className="mt-1 text-xs text-muted-foreground">
              {s.delivered_minutes} of {s.planned_minutes} minutes{s.unfulfilled_note ? ` · Not delivered: ${s.unfulfilled_note}` : ""}
            </div>
          )}
        </>
      ),
    },
    { h: "Batch", c: (s) => mono(s.batch.batch_code) },
    { h: "Trainer", c: (s) => s.trainer.full_name },
    {
      h: "Meet",
      c: (s) =>
        s.mode === "Classroom" ? (
          "—"
        ) : (
          <>
            <MeetBadge session={s} />
            <div className="mt-1 text-xs text-muted-foreground">{s.organizer_email}</div>
          </>
        ),
    },
    { h: "State", c: (s) => <StateBadge label={s.state_label} /> },
  ];
  if (withBranch) cols.splice(3, 0, { h: "Branch", c: (s) => s.branch.branch_name });
  if (actions) cols.push({ h: "Actions", c: (s) => <SessionActions session={s} manager={actions.manager} trainer={actions.trainer} /> });
  return cols;
}

export function SessionsTable({
  rows,
  actions,
  caption,
  withBranch,
}: {
  rows: ClassSession[];
  actions: { manager: boolean; trainer: boolean } | null;
  caption: string;
  withBranch?: boolean;
}) {
  return <DataTable caption={caption} rows={rows} getKey={(s) => s.session_id} cols={sessionColumns(actions, withBranch)} empty="No class sessions match." />;
}

// ---------------------------------------------------------------- reschedule requests

export function RequestsPanel({ manager, query }: { manager: boolean; query?: Record<string, string> }) {
  const requests = useQuery({ queryKey: ["delivery", "requests", query], queryFn: () => deliveryApi.requests({ status: "Open", ...query }) });
  const approve = useDelivery((id: number) => deliveryApi.approveRequest(id), "Approved — the session moved and everyone was told");
  const reject = useDelivery((v: { id: number; note: string }) => deliveryApi.rejectRequest(v.id, v.note), "Request rejected");
  const cols: Column<RescheduleRequest>[] = [
    { h: "Session", c: (r) => `${r.session.title} (${r.session.session_code})` },
    { h: "Now", c: (r) => fmtRange(r.session.starts_at, r.session.ends_at) },
    { h: "Proposed", c: (r) => fmtRange(r.proposed_starts_at, r.proposed_ends_at) },
    { h: "Trainer", c: (r) => r.requested_by.full_name },
    { h: "Reason", c: (r) => r.reason },
  ];
  if (manager)
    cols.push({
      h: "Decision",
      c: (r) => (
        <div className="flex gap-1.5">
          <Button size="sm" onClick={() => approve.mutate(r.request_id)}>
            Approve
          </Button>
          <ActionDialog
            trigger={
              <Button size="sm" variant="outline">
                Reject
              </Button>
            }
            title="Reject the reschedule request"
            fields={[{ name: "note", label: "Note to the trainer", type: "textarea", required: true }]}
            submitLabel="Reject"
            onSubmit={(v) => reject.mutateAsync({ id: r.request_id, note: v["note"]! })}
          />
        </div>
      ),
    });
  return (
    <QueryView query={requests}>
      {(page) => (
        <DataTable caption="Open reschedule requests" rows={page.data} getKey={(r) => r.request_id} cols={cols} empty="No open reschedule requests." />
      )}
    </QueryView>
  );
}

// ---------------------------------------------------------------- roster

export function RosterDialog({ batch }: { batch: Pick<Batch, "batch_id" | "batch_code" | "capacity" | "allocated_count"> }) {
  const roster = useQuery({ queryKey: ["delivery", "roster", batch.batch_id], queryFn: () => deliveryApi.roster(batch.batch_id, { status: "Active" }) });
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          Students ({batch.allocated_count})
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Students of {batch.batch_code}</DialogTitle>
          <DialogDescription>
            {batch.allocated_count} of {batch.capacity} seats taken.
          </DialogDescription>
        </DialogHeader>
        <QueryView query={roster}>
          {(page) => (
            <DataTable
              caption="Batch roster"
              rows={page.data}
              getKey={(r) => r.allocation_id}
              empty="No students allocated yet."
              cols={[
                { h: "Student", c: (r) => `${r.student.full_name} (${r.student.student_code})` },
                { h: "Enrolment", c: (r) => r.enrolment.enrolment_code },
                { h: "Status", c: (r) => <StatusBadge domain="enrolment" code={r.enrolment.status} /> },
                { h: "Joined", c: (r) => (r.enrolment.joining_date ? fmtDay(r.enrolment.joining_date) : `since ${fmtDay(r.effective_from)}`) },
              ]}
            />
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}

/** The scheduled end, or now when the class closes early; at least a minute after the start (inputs are to the minute). */
function logEnd(start: string, scheduledEnd: string): string {
  const end = Math.min(new Date(scheduledEnd).getTime(), Date.now());
  return new Date(Math.max(end, new Date(start).getTime() + 60_000)).toISOString();
}
