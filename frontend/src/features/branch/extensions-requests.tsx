/** Access extensions: requests to extend a student's access to recordings or materials. Within the Branch Manager's limit they decide; beyond it they recommend and the Founder decides. */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { contentApi, type StaffExtensionRequest } from "@/api/content";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Field, NativeSelect } from "@/components/lms/forms";
import { PillTabs, QueryView, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { Pager } from "@/features/shared/pager";

const PER_PAGE = 15;
const PARTS = ["waiting", "decided"] as const;
const PART_LABELS = { waiting: "Waiting", decided: "Decided" };
const KIND = { Recording: "recording", Material: "material", Both: "recording and material" } as const;
const firstName = (r: StaffExtensionRequest) => r.student.full_name.split(" ")[0];
const invalidate = [["access-extensions"], ["founder"], ["nav"], ["branch"]];

function RecommendDialog({ request, onClose }: { request: StaffExtensionRequest; onClose: () => void }) {
  const before = request.recommendation;
  const [decision, setDecision] = useState<"approve" | "reject" | "">(before?.decision ?? "");
  const [note, setNote] = useState(before?.note ?? "");
  const [expiry, setExpiry] = useState(before?.expiry ?? "");
  const save = useApiMutation(
    () =>
      contentApi.recommend(request.request_id, {
        decision: decision as "approve" | "reject",
        note: note.trim(),
        ...(decision === "approve" && expiry ? { expiry } : {}),
      }),
    {
      success: "Recommendation saved",
      next: "The request is with the Founder. You can change your recommendation until they decide.",
      invalidate,
      onSuccess: onClose,
    },
  );
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{before ? "Change your recommendation" : "Add your recommendation"}</DialogTitle>
          <DialogDescription>
            {request.student.full_name} asks for {KIND[request.scope]} access after the standard end date. This is beyond what you can approve, so the Founder
            decides with your advice.
          </DialogDescription>
        </DialogHeader>
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">What do you recommend?</legend>
          {(
            [
              ["approve", "I recommend approving"],
              ["reject", "I recommend rejecting"],
            ] as const
          ).map(([value, label]) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input type="radio" name="recommendation" value={value} checked={decision === value} onChange={() => setDecision(value)} />
              {label}
            </label>
          ))}
        </fieldset>
        <Field label="Why (the Founder reads this)" htmlFor="recommend-note">
          <Textarea id="recommend-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        {decision === "approve" && (
          <Field label="Suggested end date (optional)" htmlFor="recommend-expiry" hint="The date you think access should run to.">
            <Input id="recommend-expiry" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
          </Field>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!decision || !note.trim() || save.isPending} onClick={() => save.mutate(undefined)}>
            Save recommendation
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Actions({ request }: { request: StaffExtensionRequest }) {
  const [recommending, setRecommending] = useState(false);
  const decide = useApiMutation(
    (v: { decision: "approve" | "reject"; note?: string; expiry?: string }) =>
      contentApi.decide(request.request_id, { decision: v.decision, ...(v.note ? { note: v.note } : {}), ...(v.expiry ? { new_expiry: v.expiry } : {}) }),
    {
      success: (r) => (r.status === "Approved" ? `Access extended to ${fmtDate(r.approved_expiry)}` : "Extension not approved"),
      next: (r) => (r.status === "Approved" ? `${firstName(request)} has been told.` : `${firstName(request)} has been told, with your reason.`),
      invalidate,
    },
  );
  const kind = KIND[request.scope];
  const reject = (
    <FormDialog
      trigger={
        <Button size="sm" variant="outline" aria-label={`Reject the request from ${request.student.full_name}`}>
          Reject
        </Button>
      }
      title={`Reject the request from ${request.student.full_name}?`}
      description={`${firstName(request)} will be told it was not approved, and sees your reason.`}
      submitLabel="Reject request"
      destructive
      fields={[{ name: "note", label: "Reason", kind: "textarea", required: true }]}
      onSubmit={(v) => decide.mutateAsync({ decision: "reject", note: v["note"] })}
    />
  );

  if (request.can_decide && request.limit === "within") {
    const date = request.new_end_date ? fmtDate(request.new_end_date) : "the standard end date";
    return (
      <div className="flex flex-wrap gap-2">
        <ConfirmDialog
          title={`Extend access to ${date}?`}
          consequence={`The student will be told. ${firstName(request)}'s ${kind} access then runs until ${date}.`}
          confirmLabel="Extend access"
          onConfirm={() => decide.mutateAsync({ decision: "approve" })}
        >
          <Button size="sm" disabled={decide.isPending} aria-label={`Approve the request from ${request.student.full_name}`}>
            Approve
          </Button>
        </ConfirmDialog>
        {reject}
      </div>
    );
  }
  if (request.can_decide) {
    // Beyond the Branch Manager's limit: the Founder or a Super Admin states the new end date
    return (
      <div className="flex flex-wrap gap-2">
        <FormDialog
          trigger={
            <Button size="sm" aria-label={`Approve the request from ${request.student.full_name}`}>
              Approve
            </Button>
          }
          title="Extend access?"
          description={`Pick the date ${firstName(request)}'s ${kind} access will run to. The student will be told.`}
          submitLabel="Extend access"
          fields={[
            { name: "expiry", label: "New end date", kind: "date", required: true, initial: request.recommendation?.expiry ?? "" },
            { name: "note", label: "Note to the student (optional)", kind: "textarea" },
          ]}
          onSubmit={(v) => decide.mutateAsync({ decision: "approve", expiry: v["expiry"], ...(v["note"]?.trim() ? { note: v["note"].trim() } : {}) })}
        />
        {reject}
      </div>
    );
  }
  if (request.can_recommend)
    return (
      <>
        <Button size="sm" onClick={() => setRecommending(true)}>
          {request.recommendation ? "Change recommendation" : "Add recommendation"}
        </Button>
        {recommending && <RecommendDialog request={request} onClose={() => setRecommending(false)} />}
      </>
    );
  return <p className="text-sm text-muted-foreground">Decided by the Founder or a Super Admin</p>;
}

function Recommendation({ request }: { request: StaffExtensionRequest }) {
  const r = request.recommendation;
  if (!r) return null;
  return (
    <p className="rounded-lg bg-muted/50 px-3 py-2 text-sm">
      <span className="font-medium">
        {r.by?.full_name ?? "The Branch Manager"} recommends {r.decision === "approve" ? "approving" : "rejecting"}
      </span>
      {r.expiry ? ` until ${fmtDate(r.expiry)}` : ""}
      {r.note ? `: ${r.note}` : "."}
    </p>
  );
}

function RequestCard({ request }: { request: StaffExtensionRequest }) {
  const pending = request.status === "Pending";
  const kind = KIND[request.scope];
  return (
    <li className="space-y-2 rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">
            {request.student.full_name} <span className="font-mono text-xs text-muted-foreground">{request.student.student_code}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            {request.enrolment.course.title} · asks for {kind} access · <span className="font-mono text-xs">{request.request_code}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-1">
          {pending && request.with_founder && <Tag tone="info">With the Founder</Tag>}
          {pending && request.limit === "beyond" && !request.with_founder && <Tag tone="warning">Beyond your limit</Tag>}
          {!pending && (
            <StatusBadge
              domain="approval"
              code={request.status}
              label={request.status === "Approved" ? `Approved until ${fmtDate(request.approved_expiry)}` : "Not approved"}
            />
          )}
        </div>
      </div>
      <p className="text-sm">“{request.reason}”</p>
      {pending && request.current_end_date && <p className="text-xs text-muted-foreground">Access now ends on {fmtDate(request.current_end_date)}.</p>}
      {pending && request.limit === "within" && request.can_decide && (
        <p className="text-sm">
          Approving extends {kind} access to {request.new_end_date ? fmtDate(request.new_end_date) : "the standard end date"}. {firstName(request)} will be
          told.
        </p>
      )}
      {pending && request.limit === "beyond" && request.can_recommend && (
        <p className="text-sm">This is beyond what you can approve. Add your recommendation and it goes to the Founder.</p>
      )}
      {pending && request.limit === "beyond" && !request.can_recommend && !request.can_decide && (
        <p className="text-sm text-muted-foreground">This is beyond what a Branch Manager can approve. It waits for the Founder.</p>
      )}
      <Recommendation request={request} />
      {!pending && request.decided_by && (
        <p className="text-xs text-muted-foreground">
          Decided by {request.decided_by.full_name}
          {request.decision_note ? `: ${request.decision_note}` : ""}
        </p>
      )}
      {pending && <Actions request={request} />}
    </li>
  );
}

export function ExtensionsTab({ branchId }: { branchId: number | null }) {
  const [part, setPart] = useState<(typeof PARTS)[number]>("waiting");
  const [outcome, setOutcome] = useState("Approved");
  const [page, setPage] = useState(1);
  const status = part === "waiting" ? "Pending" : outcome;
  const query = useQuery({
    queryKey: ["access-extensions", "staff", { status, page, branchId }],
    queryFn: () => contentApi.staffRequests({ status, page, per_page: PER_PAGE, branch_id: branchId }),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <PillTabs
          label="Access extension requests"
          tabs={PARTS}
          labels={PART_LABELS}
          value={part}
          onChange={(next) => (setPart(next), setPage(1))}
          counts={part === "waiting" && query.data ? { waiting: query.data.meta.total } : undefined}
        />
        {part === "decided" && (
          <div className="mb-4 w-44">
            <NativeSelect
              aria-label="Outcome"
              value={outcome}
              onChange={(e) => (setOutcome(e.target.value), setPage(1))}
              options={[
                { value: "Approved", label: "Approved" },
                { value: "Rejected", label: "Not approved" },
              ]}
            />
          </div>
        )}
      </div>
      <QueryView
        query={query}
        skeleton="cards"
        isEmpty={(r) => r.data.length === 0}
        empty={
          part === "waiting"
            ? "No access extension is waiting. When a student asks for more time on recordings or materials, it appears here."
            : "Nothing has been decided in this group yet."
        }
      >
        {(result) => (
          <div className="space-y-3">
            <ul className="space-y-3" aria-label="Access extension requests">
              {result.data.map((r) => (
                <RequestCard key={r.request_id} request={r} />
              ))}
            </ul>
            <Pager meta={result.meta} onPage={setPage} noun="requests" />
          </div>
        )}
      </QueryView>
    </div>
  );
}
