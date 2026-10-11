/** What a Branch Manager does to one class: one primary action for what the class needs now, and a menu for the rest. */
import { useState, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { MoreHorizontal } from "lucide-react";
import { deliveryApi, type ClassLog, type ClassSession } from "@/api/delivery";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ActionDialog, MeetBadge, StateBadge, fmtRange, fromIstInput, toIstInput, useCanManage, useIsManager } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";

const START_OPENS_MS = 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

type DialogKind = "reschedule" | "cancel" | "link" | "deliver" | "waive" | "reject" | "failed" | "details";

export type PrimaryKey = "approve" | "link" | "confirm" | "replace" | "start";

/** The one thing a class needs most, or null when it needs nothing from the Branch Manager. */
export function primaryFor(session: ClassSession, manager: boolean, approver: boolean): { key: PrimaryKey; label: string } | null {
  if (!manager) return null;
  const open = session.state === "Scheduled" || session.state === "Rescheduled";
  if (session.approval_status === "Pending" && open) return approver ? { key: "approve", label: `Approve ${session.purpose.toLowerCase()} class` } : null;
  if (open && session.mode !== "Classroom" && session.meet_status !== "Linked") return { key: "link", label: "Add Meet link" };
  if (open && !session.confirmed_at) return { key: "confirm", label: "Confirm" };
  if (session.state === "Cancelled" && !session.replacement_waiver && session.approval_status !== "Rejected")
    return { key: "replace", label: "Plan a replacement" };
  return null;
}

/** The Meet link of an online class, set in place. Used by the schedule menu and by Class day. */
export type MeetLinkTarget = Pick<ClassSession, "session_id" | "title"> & { organizer_email?: string | null; meet_link?: string | null };

export function MeetLinkDialog({
  session,
  open,
  onOpenChange,
  trigger,
}: {
  session: MeetLinkTarget;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: ReactNode;
}) {
  const link = useDelivery((v: { id: number; link: string }) => deliveryApi.meetLink(v.id, v.link), "Meet link saved");
  return (
    <ActionDialog
      {...(trigger ? { trigger } : {})}
      {...(open !== undefined ? { open } : {})}
      {...(onOpenChange ? { onOpenChange } : {})}
      title={`Meet link for "${session.title}"`}
      description={`Paste the link from the branch's Meet mailbox${session.organizer_email ? ` (${session.organizer_email})` : ""}. The trainer and students see it as soon as it is saved. A link another batch's open class already uses is refused.`}
      fields={[{ name: "link", label: "Meet link", required: true, placeholder: "https://meet.google.com/abc-defg-hij", value: session.meet_link ?? "" }]}
      submitLabel="Save link"
      onSubmit={(v) => link.mutateAsync({ id: session.session_id, link: v["link"]! })}
    />
  );
}

export function ClassActions({
  session,
  onReplace,
  withDetails = true,
}: {
  session: ClassSession;
  /** Opens "New class" for a replacement of this cancelled class. */
  onReplace?: (session: ClassSession) => void;
  withDetails?: boolean;
}) {
  const manager = useCanManage();
  const approver = useIsManager();
  const [dialog, setDialog] = useState<DialogKind | null>(null);
  const close = (open: boolean) => !open && setDialog(null);

  const confirm = useDelivery((id: number) => deliveryApi.confirmSession(id), "Class confirmed");
  const decide = useDelivery(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => deliveryApi.decidePurpose(v.id, { decision: v.decision, note: v.note }),
    "Decision recorded",
  );
  const start = useDelivery((id: number) => deliveryApi.startSession(id), "Class started");
  const deliver = useDelivery((v: { id: number; log: ClassLog }) => deliveryApi.deliverSession(v.id, v.log), "Class logged as held");
  const reschedule = useDelivery(
    (v: { id: number; body: Parameters<typeof deliveryApi.reschedule>[1] }) => deliveryApi.reschedule(v.id, v.body),
    "Class moved. The students and the trainer have been told.",
  );
  const cancel = useDelivery(
    (v: { id: number; body: Parameters<typeof deliveryApi.cancelSession>[1] }) => deliveryApi.cancelSession(v.id, v.body),
    "Class cancelled. The students and the trainer have been told.",
  );
  const waive = useDelivery((v: { id: number; reason: string }) => deliveryApi.waiveReplacement(v.id, v.reason), "Recorded: no replacement needed");
  const failed = useDelivery(
    (v: { id: number; detail: string }) => deliveryApi.meetFailed(v.id, v.detail),
    "Marked as failed. The branch has a recovery task.",
  );
  const reset = useDelivery((id: number) => deliveryApi.meetReset(id), "Meet link reset");

  const open = session.state === "Scheduled" || session.state === "Rescheduled";
  const awaiting = session.approval_status === "Pending";
  const online = session.mode !== "Classroom";
  const started = Date.now() >= new Date(session.starts_at).getTime();
  const within24 = new Date(session.starts_at).getTime() - Date.now() < DAY_MS;
  const canStart = manager && open && !awaiting && Date.now() >= new Date(session.starts_at).getTime() - START_OPENS_MS;
  const canDeliver = manager && (session.state === "Live" || (open && started && !awaiting));
  const primary = primaryFor(session, manager, approver);

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
      label: "What happens next for the students",
      type: "textarea" as const,
      required: within24,
      hint: within24 ? "Needed because the class starts within 24 hours" : "Only needed when the class starts within 24 hours",
    },
  ];
  const emergency = (v: Record<string, string>) => ({ emergency_reason: v["emergency_reason"] || undefined, next_action: v["next_action"] || undefined });

  const primaryButton = () => {
    if (!primary) return null;
    switch (primary.key) {
      case "approve":
        return (
          <ConfirmDialog
            title={`Approve this ${session.purpose.toLowerCase()} class?`}
            consequence="The students and the trainer are told and the class appears in their schedule."
            confirmLabel="Approve"
            onConfirm={() => decide.mutateAsync({ id: session.session_id, decision: "Approved" })}
          >
            <Button size="sm">{primary.label}</Button>
          </ConfirmDialog>
        );
      case "link":
        return (
          <Button size="sm" onClick={() => setDialog("link")}>
            {primary.label}
          </Button>
        );
      case "confirm":
        return (
          <Button size="sm" disabled={confirm.isPending} onClick={() => confirm.mutate(session.session_id)}>
            {primary.label}
          </Button>
        );
      case "replace":
        return (
          <Button size="sm" onClick={() => onReplace?.(session)} disabled={!onReplace}>
            {primary.label}
          </Button>
        );
      default:
        return null;
    }
  };

  const times = [
    { name: "starts_at", label: "New start (IST)", type: "datetime" as const, required: true, value: toIstInput(session.starts_at) },
    { name: "ends_at", label: "New end (IST)", type: "datetime" as const, required: true, value: toIstInput(session.ends_at) },
  ];
  const overrideField = { name: "override_reason", label: "Why the warning is acceptable", type: "textarea" as const, required: true, afterWarnings: true };

  const hasMenu = withDetails || (manager && (open || canStart || canDeliver || session.state === "Cancelled" || (online && open)));
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {primaryButton()}
      {hasMenu && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline" aria-label={`More actions for ${session.title}`}>
              <MoreHorizontal className="size-4" aria-hidden />
              <span className="hidden sm:inline">More</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {withDetails && <DropdownMenuItem onSelect={() => setDialog("details")}>Details</DropdownMenuItem>}
            {manager && open && !awaiting && <DropdownMenuItem onSelect={() => setDialog("reschedule")}>Move to another time</DropdownMenuItem>}
            {manager && open && <DropdownMenuItem onSelect={() => setDialog("cancel")}>Cancel class</DropdownMenuItem>}
            {manager && open && online && primary?.key !== "link" && <DropdownMenuItem onSelect={() => setDialog("link")}>Change Meet link</DropdownMenuItem>}
            {canStart && <DropdownMenuItem onSelect={() => start.mutate(session.session_id)}>Start class</DropdownMenuItem>}
            {canDeliver && <DropdownMenuItem onSelect={() => setDialog("deliver")}>Log as held</DropdownMenuItem>}
            {manager && open && !session.confirmed_at && !awaiting && primary?.key !== "confirm" && (
              <DropdownMenuItem onSelect={() => confirm.mutate(session.session_id)}>Confirm</DropdownMenuItem>
            )}
            {approver && awaiting && open && <DropdownMenuItem onSelect={() => setDialog("reject")}>Do not approve</DropdownMenuItem>}
            {manager && session.state === "Cancelled" && !session.replacement_waiver && session.approval_status !== "Rejected" && (
              <DropdownMenuItem onSelect={() => setDialog("waive")}>No replacement needed</DropdownMenuItem>
            )}
            {manager && open && online && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => setDialog("failed")}>The Meet link failed</DropdownMenuItem>
                {(session.meet_status === "Linked" || session.meet_status === "Unavailable") && (
                  <DropdownMenuItem onSelect={() => reset.mutate(session.session_id)}>
                    {session.meet_status === "Linked" ? "Remove the Meet link" : "Try the Meet link again"}
                  </DropdownMenuItem>
                )}
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      {dialog === "reschedule" && (
        <ActionDialog
          open
          onOpenChange={close}
          title={`Move "${session.title}"`}
          description="The batch's students and the trainer are told, and the old time stays in the class history. A booked room or a student clash is a warning you can accept with a reason."
          fields={[...times, reasonField, ...emergencyFields, ...(approver ? [overrideField] : [])]}
          submitLabel="Move class"
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
      )}
      {dialog === "cancel" && (
        <ActionDialog
          open
          onOpenChange={close}
          title={`Cancel "${session.title}"?`}
          description="The students and the trainer are told. A cancelled class is not a student absence, and it stays owed as a replacement until you plan one or record that none is needed."
          fields={[reasonField, ...emergencyFields]}
          submitLabel="Cancel class"
          onSubmit={(v) => cancel.mutateAsync({ id: session.session_id, body: { reason: v["reason"]!, ...emergency(v) } })}
        />
      )}
      {dialog === "link" && <MeetLinkDialog session={session} open onOpenChange={close} />}
      {dialog === "failed" && (
        <ActionDialog
          open
          onOpenChange={close}
          title="The Meet link failed"
          description="The branch's Branch Managers get a recovery task."
          fields={[{ name: "detail", label: "What went wrong", type: "textarea", required: true }]}
          submitLabel="Mark failed"
          onSubmit={(v) => failed.mutateAsync({ id: session.session_id, detail: v["detail"]! })}
        />
      )}
      {dialog === "reject" && (
        <ActionDialog
          open
          onOpenChange={close}
          title={`Do not approve the ${session.purpose.toLowerCase()} class`}
          description="Students never see it and it owes nothing."
          fields={[{ name: "note", label: "Why", type: "textarea", required: true }]}
          submitLabel="Do not approve"
          onSubmit={(v) => decide.mutateAsync({ id: session.session_id, decision: "Rejected", note: v["note"] })}
        />
      )}
      {dialog === "waive" && (
        <ActionDialog
          open
          onOpenChange={close}
          title="No replacement needed"
          description="This stops the cancelled class from being listed as owing a replacement."
          fields={[reasonField]}
          submitLabel="Record"
          onSubmit={(v) => waive.mutateAsync({ id: session.session_id, reason: v["reason"]! })}
        />
      )}
      {dialog === "deliver" && (
        <ActionDialog
          open
          onOpenChange={close}
          title={`Log "${session.title}" as held`}
          description="Records that the class was held in full. The trainer's own class log, when there is one, gives the detail. Attendance is marked separately."
          fields={[
            { name: "actual_start", label: "Actual start (IST)", type: "datetime", value: toIstInput(session.live_at ?? session.starts_at) },
            { name: "actual_end", label: "Actual end (IST)", type: "datetime", value: toIstInput(session.ends_at) },
            { name: "notes", label: "Notes (topics covered)", type: "textarea" },
          ]}
          submitLabel="Log as held"
          onSubmit={(v) =>
            deliver.mutateAsync({
              id: session.session_id,
              log: {
                outcome: "Held",
                actual_start: v["actual_start"] ? fromIstInput(v["actual_start"]) : undefined,
                actual_end: v["actual_end"] ? fromIstInput(v["actual_end"]) : undefined,
                notes: v["notes"] || undefined,
              },
            })
          }
        />
      )}
      {dialog === "details" && <ClassDetails session={session} onClose={() => setDialog(null)} onReplace={onReplace} />}
    </div>
  );
}

const fmt = (iso: string | null | undefined) => (iso ? fmtRange(iso, iso).split(" · ")[0] : "—");

/** One class in full: when, who, where, what changed; the IDs of other systems sit under Advanced. */
export function ClassDetails({ session, onClose, onReplace }: { session: ClassSession; onClose: () => void; onReplace?: (s: ClassSession) => void }) {
  const detail = useQuery({ queryKey: ["delivery", "session", session.session_id], queryFn: () => deliveryApi.session(session.session_id) });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{session.title}</DialogTitle>
          <DialogDescription>
            {fmtRange(session.starts_at, session.ends_at)} · {session.batch.display_name ?? session.batch.batch_code}
          </DialogDescription>
        </DialogHeader>
        <QueryView query={detail} skeleton="detail">
          {(d) => (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <StateBadge label={d.state_label} />
                {d.mode !== "Classroom" && <MeetBadge session={d} />}
                {d.purpose !== "Regular" && <span className="rounded-full border px-2 py-0.5 text-xs">{d.purpose} class</span>}
                {d.approval_status === "Pending" && <StatusBadge domain="approval" code="Pending" label="Waiting for approval" />}
              </div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
                <dt className="text-muted-foreground">Batch</dt>
                <dd>
                  <Link to="/branch/batches/$id" params={{ id: String(d.batch.batch_id) }} className="text-primary underline-offset-2 hover:underline">
                    {d.batch.display_name ?? d.batch.batch_code}
                  </Link>
                </dd>
                <dt className="text-muted-foreground">Trainer</dt>
                <dd>{d.trainer.full_name}</dd>
                <dt className="text-muted-foreground">Topic</dt>
                <dd>{d.topic ? d.topic.title : "Not linked to a topic"}</dd>
                <dt className="text-muted-foreground">Where</dt>
                <dd>
                  {d.mode}
                  {d.room ? ` · ${d.room}` : ""}
                </dd>
                {d.mode !== "Classroom" && (
                  <>
                    <dt className="text-muted-foreground">Meet link</dt>
                    <dd className="break-all">{d.meet_link ?? "Not set yet"}</dd>
                  </>
                )}
                <dt className="text-muted-foreground">Students</dt>
                <dd>{d.allocated_count} in the batch</dd>
                {d.purpose_reference && (
                  <>
                    <dt className="text-muted-foreground">What it is for</dt>
                    <dd>{d.purpose_reference}</dd>
                  </>
                )}
                {d.replacement_waiver && (
                  <>
                    <dt className="text-muted-foreground">Replacement</dt>
                    <dd>Not needed: {d.replacement_waiver}</dd>
                  </>
                )}
              </dl>
              {(d.changes ?? []).length > 0 && (
                <div>
                  <h3 className="mb-1 font-semibold">What changed</h3>
                  <ul className="space-y-1 text-muted-foreground">
                    {(d.changes ?? []).map((c) => (
                      <li key={c.change_id}>
                        {c.change_type}: {c.reason}
                        {c.new_starts_at ? ` (now ${fmt(c.new_starts_at)})` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <details className="rounded-lg border px-3 py-2">
                <summary className="cursor-pointer font-medium">Advanced</summary>
                <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 break-all text-xs">
                  <dt className="text-muted-foreground">Class ID</dt>
                  <dd className="font-mono">{d.session_code}</dd>
                  <dt className="text-muted-foreground">Originally planned</dt>
                  <dd>{fmtRange(d.original_starts_at, d.original_ends_at)}</dd>
                  <dt className="text-muted-foreground">Meet space ID</dt>
                  <dd className="font-mono">{d.meet_space_id ?? "—"}</dd>
                  <dt className="text-muted-foreground">Calendar event ID</dt>
                  <dd className="font-mono">{d.calendar_event_id ?? "—"}</dd>
                  <dt className="text-muted-foreground">Calendar series ID</dt>
                  <dd className="font-mono">{d.calendar_series_id ?? "—"}</dd>
                  <dt className="text-muted-foreground">Conference record ID</dt>
                  <dd className="font-mono">{d.conference_record_id ?? "—"}</dd>
                </dl>
              </details>
              <ClassActions session={d} onReplace={onReplace} withDetails={false} />
            </div>
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}
