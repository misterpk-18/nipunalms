/** An access extension beyond the Branch Manager's limit: their recommendation, then the Founder's decision with the new end date. */
import { useState } from "react";
import { contentApi, type StaffExtensionRequest } from "@/api/content";
import { Field } from "@/components/lms/forms";
import { KeyValue, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fmtDate, fmtDateTime } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { ApproveRejectBar } from "./decision-bar";
import { PanelFrame, PanelPart } from "./panel-frame";

const INVALIDATE = [["founder"], ["nav"], ["access-extensions"], ["branch"]];
const KIND = { Recording: "recordings", Material: "materials", Both: "recordings and materials" } as const;

/** Approving needs an end date: the Branch Manager's suggestion is filled in when there is one, and you can change it. */
function ExtendDialog({
  request,
  busy,
  onApprove,
}: {
  request: StaffExtensionRequest;
  busy: boolean;
  onApprove: (expiry: string, note: string) => Promise<unknown>;
}) {
  const [open, setOpen] = useState(false);
  const [expiry, setExpiry] = useState(request.recommendation?.expiry ?? "");
  const [note, setNote] = useState("");
  const first = request.student.full_name.split(" ")[0];
  const submit = async () => {
    try {
      await onApprove(expiry, note.trim());
      setOpen(false);
    } catch {
      /* the mutation already showed the message */
    }
  };
  return (
    <>
      <Button disabled={busy} className="min-w-28" onClick={() => setOpen(true)}>
        Approve
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Extend access?</DialogTitle>
            <DialogDescription>
              Pick the date {first}'s {KIND[request.scope]} access will run to. {first} is told.
            </DialogDescription>
          </DialogHeader>
          <Field
            label="New end date"
            htmlFor="extend-expiry"
            hint={request.recommendation?.expiry ? `The Branch Manager suggested ${fmtDate(request.recommendation.expiry)}.` : undefined}
          >
            <Input id="extend-expiry" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
          </Field>
          <Field label="Note to the student (optional)" htmlFor="extend-note">
            <Textarea id="extend-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={busy || !expiry} onClick={() => void submit()}>
              Extend access
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function AccessPanel({ request, onClose }: { request: StaffExtensionRequest; onClose: () => void }) {
  const first = request.student.full_name.split(" ")[0];
  const decide = useApiMutation(
    (v: { decision: "approve" | "reject"; expiry?: string; note?: string }) =>
      contentApi.decide(request.request_id, { decision: v.decision, ...(v.note ? { note: v.note } : {}), ...(v.expiry ? { new_expiry: v.expiry } : {}) }),
    {
      success: (r) => (r.status === "Approved" ? `Access extended to ${fmtDate(r.approved_expiry)}` : "Extension not approved"),
      next: (r) => (r.status === "Approved" ? `${first} has been told.` : `${first} has been told, with your reason.`),
      invalidate: INVALIDATE,
      onSuccess: onClose,
    },
  );
  const rec = request.recommendation;
  return (
    <PanelFrame
      open
      onClose={onClose}
      title={`Access beyond two years for ${request.student.full_name}`}
      description={`${request.enrolment.course.title} · asks for ${KIND[request.scope]} · ${request.branch.branch_name}`}
      bar={
        request.can_decide ? (
          <ApproveRejectBar
            busy={decide.isPending}
            approve={{
              custom: (
                <ExtendDialog
                  request={request}
                  busy={decide.isPending}
                  onApprove={(expiry, note) => decide.mutateAsync({ decision: "approve", expiry, note })}
                />
              ),
            }}
            reject={{
              title: `Reject the request from ${request.student.full_name}?`,
              consequence: `${first} is told it was not approved, and sees your reason.`,
              onReject: (note) => decide.mutateAsync({ decision: "reject", note }),
            }}
          />
        ) : (
          <p className="text-sm text-muted-foreground">You cannot decide this request.</p>
        )
      }
    >
      <KeyValue
        items={[
          ["Student", `${request.student.full_name} (${request.student.student_code})`],
          ["Access now ends", request.current_end_date ? fmtDate(request.current_end_date) : "—"],
          ["Asked on", fmtDateTime(request.requested_at)],
          ["Request", request.request_code],
        ]}
      />
      <PanelPart title="What the student says">
        <p className="text-sm">“{request.reason}”</p>
      </PanelPart>
      <PanelPart title="The Branch Manager's recommendation">
        {rec ? (
          <div className="space-y-1.5 rounded-lg bg-muted/50 px-3 py-2 text-sm">
            <Tag tone={rec.decision === "approve" ? "success" : "warning"}>{rec.decision === "approve" ? "Recommends approving" : "Recommends rejecting"}</Tag>
            <p>
              {rec.by?.full_name ?? "The Branch Manager"}
              {rec.at ? `, ${fmtDate(rec.at)}` : ""}
              {rec.note ? `: ${rec.note}` : ""}
            </p>
            {rec.expiry && <p>Suggested end date: {fmtDate(rec.expiry)}</p>}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">The Branch Manager has not added a recommendation yet. You can still decide.</p>
        )}
      </PanelPart>
    </PanelFrame>
  );
}
