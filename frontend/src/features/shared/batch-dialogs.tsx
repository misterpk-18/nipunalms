/** The dialogs behind a batch's next-step button: assign a trainer, confirm, add students from the waiting list and create classes. */
import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { branchApi, type BatchProgress, type PlannedClass } from "@/api/branch";
import { ApiError } from "@/api/client";
import { deliveryApi, type BatchDetail } from "@/api/delivery";
import { EmptyState } from "@/components/lms/empty-state";
import { Field } from "@/components/lms/forms";
import { QueryView, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ActionDialog, fmtDate, fmtDay, fmtTime, issuesOf, type DialogField } from "@/features/shared/delivery-ui";
import { useDelivery } from "@/features/shared/sessions";
import { useApiMutation } from "@/lib/mutation";
import { WaitingStudent } from "@/features/shared/waiting-student";

const INVALIDATE = [["delivery"], ["branch"], ["nav"]];

export function AssignTrainerDialog({ batch, trigger }: { batch: BatchDetail; trigger: ReactNode }) {
  const staff = useQuery({ queryKey: ["delivery", "trainers", batch.branch.branch_id], queryFn: () => deliveryApi.staff("TRAINER", batch.branch.branch_id) });
  const assign = useDelivery(
    (v: { trainer_user_id: number; role: string }) => deliveryApi.assignTrainer(batch.batch_id, v),
    "Trainer assigned. They have been told.",
  );
  const assigned = new Set(batch.trainers.map((t) => t.user_id));
  const hasLead = batch.trainers.some((t) => t.role === "Lead");
  return (
    <ActionDialog
      trigger={trigger}
      title={hasLead ? "Add a co-trainer" : "Assign a lead trainer"}
      description="Only people who hold the Trainer role at this branch can be chosen. The trainer is told, and the batch's classes are led by the lead trainer."
      fields={[
        {
          name: "trainer_user_id",
          label: "Trainer",
          type: "select",
          required: true,
          options: [
            { value: "", label: "Choose a trainer" },
            ...(staff.data ?? []).filter((s) => !assigned.has(s.user_id)).map((s) => ({ value: s.user_id, label: s.full_name })),
          ],
        },
        {
          name: "role",
          label: "Role",
          type: "select",
          options: [
            { value: "Lead", label: "Lead" },
            { value: "Co-trainer", label: "Co-trainer" },
          ],
          value: hasLead ? "Co-trainer" : "Lead",
        },
      ]}
      submitLabel="Assign"
      onSubmit={(v) => assign.mutateAsync({ trainer_user_id: Number(v["trainer_user_id"]), role: v["role"]! })}
    />
  );
}

/** Which problem keys the focused "Finish the setup" form can fix; the others (the course outline, a clash) need the full edit form. */
export const FINISHABLE = ["timetable", "resources", "recording"];

/** Only the details the batch is still missing: dates and timetable, verified seats and room, the recording statement. */
export function FinishSetupDialog({ batch, progress, trigger }: { batch: BatchDetail; progress: BatchProgress; trigger: ReactNode }) {
  const update = useDelivery((body: Record<string, unknown>) => deliveryApi.updateBatch(batch.batch_id, body), "Saved. Check the step bar for what is left.");
  const missing = new Set(progress.problems.map((p) => p.key));
  const room = batch.mode !== "Live Online";
  const online = batch.mode !== "Classroom";
  const fields: DialogField[] = [
    { name: "planned_start", label: "Starts on", type: "date", required: true, value: batch.planned_start ?? "", showIf: () => missing.has("timetable") },
    { name: "planned_end", label: "Ends on", type: "date", required: true, value: batch.planned_end ?? "", showIf: () => missing.has("timetable") },
    {
      name: "schedule_days",
      label: "Teaching days",
      type: "days",
      required: true,
      value: batch.schedule_days.join(","),
      showIf: () => missing.has("timetable"),
    },
    { name: "start_time", label: "Class starts (IST)", type: "time", required: true, value: batch.start_time ?? "", showIf: () => missing.has("timetable") },
    { name: "end_time", label: "Class ends (IST)", type: "time", required: true, value: batch.end_time ?? "", showIf: () => missing.has("timetable") },
    {
      name: "location",
      label: "Room",
      required: true,
      value: batch.location ?? "",
      hint: "The classroom or lab",
      showIf: () => missing.has("resources") && room,
    },
    {
      name: "classroom_capacity",
      label: "Seats verified in the room",
      type: "number",
      min: 1,
      required: true,
      value: batch.classroom_capacity?.toString() ?? "",
      hint: `At least the ${batch.capacity} seats of the batch`,
      showIf: () => missing.has("resources") && room,
    },
    {
      name: "online_capacity",
      label: "Online seats verified",
      type: "number",
      min: 1,
      required: true,
      value: batch.online_capacity?.toString() ?? "",
      hint: `At least the ${batch.capacity} seats of the batch`,
      showIf: () => missing.has("resources") && online,
    },
    {
      name: "recording_provision",
      label: "Will students get recordings?",
      type: "select",
      required: true,
      value: batch.recording_provision ?? "",
      options: [
        { value: "", label: "Choose" },
        { value: "Included", label: "Yes, every class" },
        { value: "Limited", label: "Some classes" },
        { value: "Not Included", label: "No" },
      ],
      showIf: () => missing.has("recording"),
    },
  ];
  const num = (v: string | undefined) => (v ? Number(v) : undefined);
  return (
    <ActionDialog
      trigger={trigger}
      title="Finish the setup"
      description="Only what the batch is still missing is asked for. You can change all of it later from the batch's Overview."
      fields={fields}
      submitLabel="Save"
      onSubmit={(v) => {
        const body: Record<string, unknown> = {};
        if (v["planned_start"]) body["planned_start"] = v["planned_start"];
        if (v["planned_end"]) body["planned_end"] = v["planned_end"];
        if (v["schedule_days"]) body["schedule_days"] = v["schedule_days"].split(",");
        if (v["start_time"]) body["start_time"] = v["start_time"];
        if (v["end_time"]) body["end_time"] = v["end_time"];
        if (v["location"]) body["location"] = v["location"].trim();
        if (num(v["classroom_capacity"])) body["classroom_capacity"] = num(v["classroom_capacity"]);
        if (num(v["online_capacity"])) body["online_capacity"] = num(v["online_capacity"]);
        if (v["recording_provision"]) body["recording_provision"] = v["recording_provision"];
        return update.mutateAsync(body);
      }}
    />
  );
}

/** Confirm in one step. Warnings are shown first and need a written reason, which is kept on record. */
export function ConfirmBatchDialog({
  batch,
  progress,
  trigger,
  approve: approver,
}: {
  batch: BatchDetail;
  progress: BatchProgress;
  trigger: ReactNode;
  approve: boolean;
}) {
  const confirm = useApiMutation((v: { note?: string; override_reason?: string }) => branchApi.confirmBatch(batch.batch_id, v), {
    success: `${batch.display_name ?? batch.batch_code} is confirmed`,
    next: "Next: add students from the waiting list, then create the classes.",
    invalidate: INVALIDATE,
  });
  const warned = progress.warnings.length > 0;
  return (
    <ActionDialog
      trigger={trigger}
      title={`Confirm ${batch.display_name ?? batch.batch_code}?`}
      description="The batch becomes Confirmed and can take students and classes. After this, changing its start date, mode, days or times needs each student's agreement."
      submitLabel="Confirm batch"
      fields={[
        {
          name: "override_reason",
          label: "Why this is acceptable",
          type: "textarea",
          required: true,
          showIf: () => warned,
          hint: "Kept on record with your name",
        },
        { name: "note", label: "Note (optional)", type: "textarea" },
      ]}
      onSubmit={(v) => confirm.mutateAsync({ note: v["note"] || undefined, override_reason: v["override_reason"] || undefined })}
    >
      {approver && warned && (
        <StatusNote tone="warning" title="Look at this before you confirm">
          <ul className="list-disc pl-5">
            {progress.warnings.map((w) => (
              <li key={w.key}>
                {w.label}: {w.detail}
              </li>
            ))}
          </ul>
        </StatusNote>
      )}
    </ActionDialog>
  );
}

/** The students on the waiting list this batch could take, each with Allocate. */
export function AddStudentsDialog({ batch, trigger }: { batch: BatchDetail; trigger: ReactNode }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: ["branch", "batch-waiting", batch.batch_id], queryFn: () => branchApi.batchWaiting(batch.batch_id), enabled: open });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add students from the waiting list</DialogTitle>
          <DialogDescription>
            {batch.display_name ?? batch.batch_code} has {query.data ? query.data.seats_left : batch.capacity - batch.allocated_count} seat(s) left. These
            students are waiting for a batch of {batch.course.title} at {batch.branch.branch_name}.
          </DialogDescription>
        </DialogHeader>
        <QueryView
          query={query}
          skeleton="cards"
          isEmpty={(d) => d.students.length === 0}
          empty="Nobody on the waiting list matches this batch yet: same course, same branch. New admissions appear here as soon as they arrive."
        >
          {(d) => (
            <ul className="space-y-3" aria-label="Students waiting for this batch">
              {d.students.map((row) => (
                <WaitingStudent key={row.enrolment.enrolment_id} row={row} manage withBranch={false} />
              ))}
            </ul>
          )}
        </QueryView>
      </DialogContent>
    </Dialog>
  );
}

function PlanTable({ classes }: { classes: PlannedClass[] }) {
  return (
    <div className="max-h-64 overflow-y-auto rounded-lg border">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Classes that would be created</caption>
        <thead className="sticky top-0 bg-muted text-xs uppercase text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-1.5">
              Date
            </th>
            <th scope="col" className="px-3 py-1.5">
              Time (IST)
            </th>
            <th scope="col" className="px-3 py-1.5">
              Class
            </th>
          </tr>
        </thead>
        <tbody>
          {classes.map((c) => (
            <tr key={c.starts_at} className="border-t align-top">
              <td className="whitespace-nowrap px-3 py-1.5">{fmtDate(c.starts_at)}</td>
              <td className="whitespace-nowrap px-3 py-1.5">
                {fmtTime(c.starts_at)}–{fmtTime(c.ends_at)}
              </td>
              <td className="px-3 py-1.5">
                {c.title}
                {c.blocked && <p className="text-xs text-danger">{c.blocked}</p>}
                {c.warnings.map((w) => (
                  <p key={w} className="text-xs text-warning">
                    {w}
                  </p>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Create classes from the batch's timetable: a preview that skips holidays and closures, then one click to create them all. */
export function CreateClassesDialog({ batch, trigger }: { batch: BatchDetail; trigger: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState("");
  const [until, setUntil] = useState("");
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (open) {
      setFrom("");
      setUntil("");
      setReason("");
    }
  }, [open]);
  const range = { ...(from ? { from_date: from } : {}), ...(until ? { until } : {}) };
  const preview = useQuery({
    queryKey: ["branch", "generate-preview", batch.batch_id, from, until],
    queryFn: () => branchApi.generate(batch.batch_id, { preview: true, ...range }),
    enabled: open,
    retry: false,
  });
  const create = useApiMutation(() => branchApi.generate(batch.batch_id, { ...range, override_reason: reason || undefined }), {
    success: (r) => `${r.created.length} classes created`,
    next: "The students and the trainer have been told.",
    view: { to: "/branch/schedule", label: "View schedule" },
    invalidate: INVALIDATE,
    onSuccess: () => setOpen(false),
    silentValidation: true,
  });
  const plan = preview.data;
  const problem = preview.error instanceof ApiError ? preview.error.message : null;
  const createIssues = issuesOf(create.error);
  const needsReason = (plan?.warnings.length ?? 0) > 0;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Create classes for {batch.display_name ?? batch.batch_code}</DialogTitle>
          <DialogDescription>
            One class on each teaching day from the batch timetable. Holidays and closures are skipped. Nothing is created until you press the button.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="From" htmlFor="gen-from" hint="Leave empty to start at the batch's start date, or today if that has passed">
            <Input id="gen-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="Until" htmlFor="gen-until" hint="Leave empty to run to the batch's end date">
            <Input id="gen-until" type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
          </Field>
        </div>
        {preview.isPending && <p className="text-sm text-muted-foreground">Working out the classes…</p>}
        {problem && (
          <StatusNote tone="warning" title="Cannot plan the classes yet">
            {problem}
          </StatusNote>
        )}
        {plan && (
          <div className="space-y-3">
            <p className="text-sm">
              <strong>
                {plan.classes.length} class{plan.classes.length === 1 ? "" : "es"}
              </strong>{" "}
              from {fmtDay(plan.from)} to {fmtDay(plan.until)}, led by {plan.trainer.full_name}
              {plan.room ? ` in ${plan.room}` : ""}.
            </p>
            {plan.classes.length === 0 ? (
              <EmptyState reason="Every teaching day in these dates is already planned, closed or past. Change the dates to plan more." />
            ) : (
              <PlanTable classes={plan.classes} />
            )}
            {plan.truncated && (
              <StatusNote tone="info">Only the first 60 classes are planned at a time. Press Create classes again afterwards for the rest.</StatusNote>
            )}
            {plan.skipped.length > 0 && (
              <details className="rounded-lg border px-3 py-2 text-sm">
                <summary className="cursor-pointer font-medium">
                  {plan.skipped.length} day{plan.skipped.length === 1 ? "" : "s"} skipped
                </summary>
                <ul className="mt-2 space-y-0.5 text-muted-foreground">
                  {plan.skipped.map((s) => (
                    <li key={s.date}>
                      {fmtDay(s.date)}: {s.reason}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {plan.blocking.length > 0 && (
              <StatusNote tone="danger" title="These classes cannot be created">
                <ul className="list-disc pl-5">
                  {plan.blocking.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </StatusNote>
            )}
            {needsReason && (
              <StatusNote tone="warning" title="Look at this before you create them">
                <ul className="list-disc pl-5">
                  {plan.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </StatusNote>
            )}
            {needsReason && (
              <Field label="Why this is acceptable *" htmlFor="gen-reason" hint="Kept on record with your name">
                <Textarea id="gen-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
              </Field>
            )}
            {createIssues && createIssues.blocking.length + createIssues.warnings.length > 0 && !plan.blocking.length && (
              <StatusNote tone="danger">{[...createIssues.blocking, ...createIssues.warnings].join(" ")}</StatusNote>
            )}
          </div>
        )}
        <DialogFooter>
          <Button
            disabled={!plan || plan.classes.length === 0 || plan.blocking.length > 0 || (needsReason && !reason.trim()) || create.isPending}
            onClick={() => create.mutate(undefined)}
          >
            {plan && plan.classes.length > 0 ? `Create ${plan.classes.length} class${plan.classes.length === 1 ? "" : "es"}` : "Create classes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
