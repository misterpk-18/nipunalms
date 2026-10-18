/** The dialogs of the academic calendar: add a holiday or closure, edit one (showing the impact first), cancel one, decide a proposal. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/api/admin";
import type { BranchRef } from "@/api/types";
import { calendarApi, calendarKeys, type Closure, type ClosureImpact, type ClosureKind } from "@/api/calendar";
import { Field, NativeSelect } from "@/components/lms/forms";
import { LoadingSkeleton, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate, fmtDateTime } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { FormDialog } from "./form-parts";

const INVALIDATE = [[...calendarKeys.all], ["admin", "needs-action"], ["nav", "counts"]];

export const classCount = (n: number) => `${n} class${n === 1 ? "" : "es"}`;
export const rangeText = (c: Pick<Closure, "starts_on" | "ends_on">) =>
  c.starts_on === c.ends_on ? fmtDate(c.starts_on) : `${fmtDate(c.starts_on)} to ${fmtDate(c.ends_on)}`;

/** From and To: To can't be before From (it follows From when From moves past it), and a window is at most 63 days. */
function DateRange({ from, to, onChange, error }: { from: string; to: string; onChange: (from: string, to: string) => void; error?: string | null }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label="From" htmlFor="cal-from">
        <Input id="cal-from" type="date" value={from} onChange={(e) => onChange(e.target.value, to && to < e.target.value ? e.target.value : to)} />
      </Field>
      <Field label="To (last day)" htmlFor="cal-to" error={error ?? undefined}>
        <Input id="cal-to" type="date" value={to} min={from || undefined} onChange={(e) => onChange(from, e.target.value)} />
      </Field>
    </div>
  );
}

const dateError = (from: string, to: string) =>
  from && to && to < from
    ? "The last day can't be before the first day."
    : from && to && (Date.parse(to) - Date.parse(from)) / 86_400_000 > 62
      ? "A closure can last at most 63 days. Add a second one for longer."
      : null;

/** `branchScope`: the one branch a closure can be proposed for (Branch Manager); null lets the person pick any branch. */
export function AddClosureDialog({
  kinds,
  branchScope,
  initialDate,
  onClose,
}: {
  kinds: ClosureKind[];
  branchScope: BranchRef | null;
  initialDate?: string;
  onClose: () => void;
}) {
  const branches = useQuery({ queryKey: ["reference", "branches"], queryFn: adminApi.branches, staleTime: 5 * 60_000, enabled: !branchScope });
  const [kind, setKind] = useState<ClosureKind>(kinds[0] ?? "Company Holiday");
  const [branchId, setBranchId] = useState(branchScope ? String(branchScope.branch_id) : "");
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("");
  const [from, setFrom] = useState(initialDate ?? "");
  const [to, setTo] = useState(initialDate ?? "");
  const holiday = kind === "Company Holiday";
  const error = dateError(from, to);
  const create = useApiMutation(calendarApi.create, {
    success: (c) => (c.status === "Approved" ? `${c.title} added to the calendar` : `${c.title} proposed`),
    next: (c) =>
      c.status === "Approved"
        ? "Branch Managers are asked to replace any classes that fall on these dates."
        : "The Super Admin or Founder decides it. It is not in force until then.",
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  const ready = !!title.trim() && !!from && !!to && !error && (holiday || !!branchId);
  return (
    <FormDialog
      title="Add holiday or closure"
      description={
        holiday
          ? "A company holiday applies to every branch. Classes on these dates are not moved for you: the Branch Managers are asked to replace them."
          : branchScope
            ? "Propose closing your branch for these dates. It waits for the Super Admin or Founder to approve it; until then classes run as scheduled."
            : "A branch closure closes one branch for these dates and takes effect at once. The Branch Managers are asked to replace any classes that fall on them."
      }
      submitLabel={branchScope ? "Propose closure" : "Add to calendar"}
      busy={create.isPending || !ready}
      onClose={onClose}
      onSubmit={() =>
        create.mutate({
          kind,
          branch_id: holiday ? null : Number(branchId),
          starts_on: from,
          ends_on: to,
          title: title.trim(),
          ...(reason.trim() ? { reason: reason.trim() } : {}),
        })
      }
    >
      {kinds.length > 1 && (
        <Field label="What is it?" htmlFor="cal-kind">
          <NativeSelect
            id="cal-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as ClosureKind)}
            options={kinds.map((k) => ({ value: k, label: k === "Company Holiday" ? "Company holiday (every branch)" : "Branch closure (one branch)" }))}
          />
        </Field>
      )}
      {!holiday && branchScope && <p className="text-sm">Branch: {branchScope.branch_name}</p>}
      {!holiday && !branchScope && (
        <Field label="Which branch is closed?" htmlFor="cal-branch">
          <NativeSelect
            id="cal-branch"
            placeholder="Pick a branch"
            value={branchId}
            onChange={(e) => setBranchId(e.target.value)}
            options={(branches.data ?? []).map((b) => ({ value: b.branch_id, label: b.branch_name }))}
          />
        </Field>
      )}
      <Field label={holiday ? "Name of the holiday" : "Why is the branch closed?"} htmlFor="cal-title">
        <Input id="cal-title" placeholder={holiday ? "Diwali" : "Flooding"} value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <DateRange
        from={from}
        to={to}
        onChange={(f, t) => {
          setFrom(f);
          setTo(t);
        }}
        error={error}
      />
      <Field label={holiday ? "Note (optional)" : "More detail (optional)"} htmlFor="cal-reason">
        <Textarea id="cal-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
    </FormDialog>
  );
}

/** What a change touches, in a sentence and the first few classes. */
function ImpactNote({ impact, verb }: { impact: ClosureImpact; verb: "edit" | "cancel" }) {
  const sessions = impact.affected_sessions.slice(0, 5);
  const live = impact.status === "Approved" || verb === "edit";
  return (
    <div className="space-y-2" data-testid="impact">
      <StatusNote tone={impact.affected_count > 0 ? "warning" : "info"}>
        {verb === "cancel" ? (
          impact.affected_count > 0 ? (
            <>
              This affects {classCount(impact.affected_count)}.{" "}
              {impact.status === "Approved" ? "They are no longer closed and run as scheduled." : "None of them were moved yet."}
            </>
          ) : (
            "No classes fall on these dates, so nothing else changes."
          )
        ) : impact.affected_count > 0 ? (
          <>
            This affects {classCount(impact.affected_count)} on the new dates.
            {(impact.newly_affected_count ?? 0) > 0 &&
              live &&
              ` ${classCount(impact.newly_affected_count ?? 0)} ${impact.newly_affected_count === 1 ? "is" : "are"} new to it: Branch Managers are asked to replace them.`}
            {(impact.freed_count ?? 0) > 0 && ` ${classCount(impact.freed_count ?? 0)} no longer fall inside it and run as scheduled.`}
          </>
        ) : (
          <>
            No classes fall on the new dates.
            {(impact.freed_count ?? 0) > 0 && ` ${classCount(impact.freed_count ?? 0)} no longer fall inside it and run as scheduled.`}
          </>
        )}
      </StatusNote>
      {sessions.length > 0 && (
        <ul className="space-y-0.5 text-sm text-muted-foreground">
          {sessions.map((s) => (
            <li key={s.session_id}>
              {s.session_code} · {s.title} · {fmtDateTime(s.starts_at)}
            </li>
          ))}
          {impact.affected_sessions.length > sessions.length && <li>and {impact.affected_sessions.length - sessions.length} more</li>}
        </ul>
      )}
    </div>
  );
}

/** Edit: change the details, press "Review the impact", then confirm. Nothing is saved until the second step. */
export function EditClosureDialog({ closure, onClose }: { closure: Closure; onClose: () => void }) {
  const [title, setTitle] = useState(closure.title);
  const [reason, setReason] = useState(closure.reason ?? "");
  const [from, setFrom] = useState(closure.starts_on);
  const [to, setTo] = useState(closure.ends_on);
  const [impact, setImpact] = useState<ClosureImpact | null>(null);
  const error = dateError(from, to);
  const body = { title: title.trim(), reason: reason.trim() || null, starts_on: from, ends_on: to };
  const review = useApiMutation(() => calendarApi.update(closure.closure_id, { ...body, dry_run: true }), { onSuccess: setImpact });
  const save = useApiMutation(() => calendarApi.update(closure.closure_id, body), {
    success: `${title.trim()} updated`,
    next: (r) =>
      (r.newly_affected_count ?? 0) > 0 && closure.status === "Approved" ? "Branch Managers are asked to replace the classes that are newly affected." : "",
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  const ready = !!title.trim() && !!from && !!to && !error;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{impact ? "Save these changes?" : `Edit ${closure.title}`}</DialogTitle>
          <DialogDescription>
            {closure.kind === "Company Holiday" ? "Company holiday, every branch." : `Branch closure at ${closure.branch?.branch_name ?? "one branch"}.`}
          </DialogDescription>
        </DialogHeader>
        {impact ? (
          <ImpactNote impact={impact} verb="edit" />
        ) : (
          <div className="grid gap-3">
            <Field label="Title" htmlFor="cal-title">
              <Input id="cal-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </Field>
            <DateRange
              from={from}
              to={to}
              onChange={(f, t) => {
                setFrom(f);
                setTo(t);
              }}
              error={error}
            />
            <Field label="Note (optional)" htmlFor="cal-reason">
              <Textarea id="cal-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={impact ? () => setImpact(null) : onClose}>
            {impact ? "Back" : "Cancel"}
          </Button>
          {impact ? (
            <Button disabled={save.isPending} onClick={() => save.mutate()}>
              Save changes
            </Button>
          ) : (
            <Button disabled={!ready || review.isPending} onClick={() => review.mutate()}>
              Review the impact
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Cancel: the impact is shown first (read from the server before anything changes), then a reason and the confirm. */
export function CancelClosureDialog({ closure, onClose }: { closure: Closure; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const preview = useQuery({
    queryKey: ["calendar", "cancel-impact", closure.closure_id],
    queryFn: () => calendarApi.cancel(closure.closure_id, { reason: "preview", dry_run: true }),
    staleTime: 0,
    gcTime: 0,
  });
  const cancel = useApiMutation(() => calendarApi.cancel(closure.closure_id, { reason: reason.trim() }), {
    success: `${closure.title} cancelled`,
    next: (r) =>
      r.affected_count > 0 && closure.status === "Approved" ? `${classCount(r.affected_count)} run as scheduled again. Branch Managers are told.` : "",
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Cancel {closure.title}?</DialogTitle>
          <DialogDescription>{rangeText(closure)}. A cancelled entry stays in the list so the history is kept.</DialogDescription>
        </DialogHeader>
        {preview.isPending ? <LoadingSkeleton kind="detail" /> : preview.data ? <ImpactNote impact={preview.data} verb="cancel" /> : null}
        <Field label="Why is it cancelled?" htmlFor="cal-cancel-reason">
          <Textarea id="cal-cancel-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Keep it
          </Button>
          <Button variant="destructive" disabled={cancel.isPending || reason.trim().length < 3 || preview.isPending} onClick={() => cancel.mutate()}>
            Cancel this entry
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function DecideClosureDialog({ closure, onClose }: { closure: Closure; onClose: () => void }) {
  const [decision, setDecision] = useState<"Approved" | "Rejected" | "">("");
  const [note, setNote] = useState("");
  const decide = useApiMutation((v: { decision: "Approved" | "Rejected" }) => calendarApi.decide(closure.closure_id, v.decision, note.trim() || undefined), {
    success: (c) => `${c.title} ${c.status.toLowerCase()}`,
    invalidate: INVALIDATE,
    onSuccess: onClose,
  });
  return (
    <FormDialog
      title={`Branch closure: ${closure.title}`}
      description={`${closure.branch?.branch_name ?? "Branch"} · ${rangeText(closure)}. Approving closes the branch on these dates and the branch's Branch Managers are asked to replace affected classes.`}
      submitLabel="Record decision"
      busy={decide.isPending || !decision || (decision === "Rejected" && note.trim().length < 3)}
      onClose={onClose}
      onSubmit={() => decision && decide.mutate({ decision })}
    >
      <Field label="Decision" htmlFor="cal-decision">
        <NativeSelect
          id="cal-decision"
          placeholder="Choose"
          value={decision}
          onChange={(e) => setDecision(e.target.value as "Approved" | "Rejected" | "")}
          options={[
            { value: "Approved", label: "Approve" },
            { value: "Rejected", label: "Reject" },
          ]}
        />
      </Field>
      <Field label={decision === "Rejected" ? "Why (required)" : "Note (optional)"} htmlFor="cal-note">
        <Textarea id="cal-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
    </FormDialog>
  );
}
