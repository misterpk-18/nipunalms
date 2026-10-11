/** What a Branch Manager does to one student in the completion pipeline: decide, approve, return, issue, and the rare actions under "More". */
import { useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { certificatesApi, COMPLETION_DECISIONS, type CompletionDecision } from "@/api/certificates";
import type { PipelineRow } from "@/api/completion-pipeline";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { FormDialog } from "@/features/shared/attendance-parts";
import { ReasonDialog } from "@/features/shared/reason-dialog";
import { useApiMutation } from "@/lib/mutation";
import { rupees } from "./completion-format";

const REFRESH = [["completion"], ["certificates"], ["nav"], ["branch"]];

const CHOICES: Record<CompletionDecision, { label: string; help: string; confirm: string }> = {
  Complete: { label: "Complete", help: "The course is finished. The certificate moves to review.", confirm: "Mark complete" },
  "Not Yet": { label: "Not yet complete", help: "The student stays in the course and the trainer is told why.", confirm: "Mark not yet complete" },
  "Needs Recovery": { label: "Needs recovery", help: "Something must be made up before the course can complete.", confirm: "Mark needs recovery" },
};

function consequence(decision: CompletionDecision, name: string): string {
  if (decision === "Complete") return `${name}'s course status becomes Completed and the certificate moves to review. ${name} is told.`;
  if (decision === "Not Yet") return `${name} stays in the course and the trainer is told.`;
  return `${name} stays in the course, marked as needing recovery, and the trainer is told.`;
}

/** Three choices, none selected for you. Anything but Complete needs a reason. A last confirm states what will happen. */
export function DecideDialog({
  open,
  onOpenChange,
  reviewId,
  name,
  trainerRecommends,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  reviewId: number | null;
  name: string;
  trainerRecommends: boolean;
}) {
  const [decision, setDecision] = useState<CompletionDecision | "">("");
  const [reason, setReason] = useState("");
  const decide = useApiMutation(
    (v: { id: number; decision: CompletionDecision; reason?: string }) => certificatesApi.decideCompletion(v.id, v.decision, v.reason),
    {
      invalidate: REFRESH,
      success: (r) => (r.decision === "Complete" ? `${name} is marked complete` : `Decision recorded for ${name}`),
      next: (r) => (r.decision === "Complete" ? "The certificate has moved to review." : "The trainer has been told."),
    },
  );
  const needsReason = decision !== "" && decision !== "Complete";
  const ready = decision !== "" && (!needsReason || reason.trim().length >= 3) && reviewId !== null;
  const close = (next: boolean) => {
    onOpenChange(next);
    if (!next) {
      setDecision("");
      setReason("");
    }
  };
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Decide: {name}</DialogTitle>
          <DialogDescription>Choose one. Nothing is chosen for you.</DialogDescription>
        </DialogHeader>
        <RadioGroup value={decision} onValueChange={(v) => setDecision(v as CompletionDecision)} aria-label="Your decision">
          {COMPLETION_DECISIONS.map((d) => (
            <Label
              key={d}
              htmlFor={`decision-${d}`}
              className="flex cursor-pointer items-start gap-3 rounded-lg border bg-card p-3 font-normal has-[[data-state=checked]]:border-primary"
            >
              <RadioGroupItem id={`decision-${d}`} value={d} className="mt-0.5" />
              <span>
                <span className="block text-sm font-medium">{CHOICES[d].label}</span>
                <span className="block text-xs text-muted-foreground">{CHOICES[d].help}</span>
              </span>
            </Label>
          ))}
        </RadioGroup>
        {decision === "Complete" && !trainerRecommends && (
          <StatusNote tone="warning" title="The trainer has not recommended Complete.">
            The system will not accept Complete until a trainer of the batch recommends it.
          </StatusNote>
        )}
        {needsReason && (
          <div className="space-y-1.5">
            <Label htmlFor="decision-reason">Reason (the trainer will see it)</Label>
            <Textarea id="decision-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
            {reason.trim().length < 3 && <p className="text-xs text-muted-foreground">Write at least 3 characters.</p>}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)}>
            Cancel
          </Button>
          <ConfirmDialog
            title={decision === "Complete" ? `Mark ${name} complete?` : decision ? `${CHOICES[decision].confirm} for ${name}?` : "Choose a decision first"}
            consequence={decision ? consequence(decision, name) : ""}
            confirmLabel={decision ? CHOICES[decision].confirm : "Confirm"}
            onConfirm={async () => {
              if (!decision || reviewId === null) return;
              try {
                await decide.mutateAsync({ id: reviewId, decision, reason: needsReason ? reason.trim() : undefined });
                close(false);
              } catch {
                /* the mutation already showed the server's message; keep the dialog open */
              }
            }}
          >
            <Button disabled={!ready}>Continue</Button>
          </ConfirmDialog>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** "Decide" (a review is open) or "Start review" (opens one, then the Decide dialog). */
export function DecideButton({ row }: { row: PipelineRow }) {
  const [open, setOpen] = useState(false);
  const [startedId, setStartedId] = useState<number | null>(null);
  const start = useApiMutation((enrolmentId: number) => certificatesApi.openReview(enrolmentId), {
    invalidate: REFRESH,
    success: `Review started for ${row.student.full_name}`,
    onSuccess: (r) => {
      setStartedId(r.review_id);
      setOpen(true);
    },
  });
  const reviewId = row.review?.review_id ?? startedId;
  const trainerOk = row.evidence?.checks.find((c) => c.key === "trainer")?.ok ?? row.review?.trainer_recommendation === "Complete";
  const canDecide = row.actions.includes("decide") || startedId !== null;
  return (
    <>
      {canDecide ? (
        <Button size="sm" onClick={() => setOpen(true)}>
          Decide
        </Button>
      ) : row.actions.includes("start_review") ? (
        <Button size="sm" disabled={start.isPending} onClick={() => start.mutate(row.enrolment.enrolment_id)}>
          Start review
        </Button>
      ) : null}
      <DecideDialog open={open} onOpenChange={setOpen} reviewId={reviewId} name={row.student.full_name} trainerRecommends={trainerOk} />
    </>
  );
}

/** Approve the certificate (Completed stage), or send it back with a reason. */
export function ApproveButtons({ row }: { row: PipelineRow }) {
  const cert = row.certificate!;
  const name = row.student.full_name;
  const approve = useApiMutation(() => certificatesApi.approve(cert.certificate_id), {
    invalidate: REFRESH,
    success: `Certificate approved for ${name}`,
    next: "It moves to Ready to issue. The number is created when you issue it.",
  });
  const back = useApiMutation((reason: string) => certificatesApi.returnToReview(cert.certificate_id, reason), {
    invalidate: REFRESH,
    success: `Certificate for ${name} returned to review`,
  });
  return (
    <>
      {row.actions.includes("approve") && (
        <ConfirmDialog
          title={`Approve the certificate for ${name}?`}
          consequence="It moves to Ready to issue. The number is created when you issue it."
          confirmLabel="Approve certificate"
          onConfirm={() => approve.mutateAsync(undefined).catch(() => undefined)}
        >
          <Button size="sm">Approve certificate</Button>
        </ConfirmDialog>
      )}
      {row.actions.includes("return") && (
        <ReasonDialog
          trigger={
            <Button size="sm" variant="outline">
              Return to review
            </Button>
          }
          title={`Return the certificate for ${name} to review`}
          description="Say what needs another look. The reviewer sees your reason."
          label="What needs another look?"
          confirmLabel="Return to review"
          busy={back.isPending}
          onSubmit={(reason) => back.mutateAsync(reason)}
        />
      )}
    </>
  );
}

export function IssueButton({ row }: { row: PipelineRow }) {
  const name = row.student.full_name;
  const issue = useApiMutation(() => certificatesApi.issue(row.certificate!.certificate_id), {
    invalidate: REFRESH,
    success: (c) => `Certificate ${c.certificate_number} issued to ${name}`,
    next: `${name} has been told.`,
    view: (c) => (c.certificate_number ? { to: `/verify/${encodeURIComponent(c.certificate_number)}`, label: "View" } : undefined),
  });
  return (
    <ConfirmDialog
      title={`Issue the certificate to ${name}?`}
      consequence={`The certificate number is created now and ${name} is told. This cannot be undone.`}
      confirmLabel="Issue certificate"
      destructive
      onConfirm={() => issue.mutateAsync(undefined).catch(() => undefined)}
    >
      <Button size="sm">Issue certificate</Button>
    </ConfirmDialog>
  );
}

type MoreDialog = "fee" | "correction" | "revocation" | "reinstatement" | null;

/** The rare actions, kept out of the way: a fee release, a correction, a revocation, a reinstatement. Only what the server allows is listed. */
export function MoreActions({ row }: { row: PipelineRow }) {
  const [dialog, setDialog] = useState<MoreDialog>(null);
  const cert = row.certificate;
  const name = row.student.full_name;
  const feeRelease = !!row.can_request_fee_exception;
  const correction = row.actions.includes("request_correction");
  const revocation = row.actions.includes("request_revocation");
  const reinstatement = row.actions.includes("request_reinstatement");
  const ask = useApiMutation(
    (v: { kind: "Correction" | "Revocation" | "Reinstatement"; reason: string; evidence?: string; holder_name?: string }) =>
      certificatesApi.requestChange(cert!.certificate_id, v),
    {
      invalidate: REFRESH,
      success: (r) => `${r.kind} requested`,
      next: "Someone else decides it. It is listed under Requests and fee releases.",
    },
  );
  const exception = useApiMutation((reason: string) => certificatesApi.requestException(cert!.certificate_id, reason), {
    invalidate: REFRESH,
    success: "Fee release requested",
    next: "The Founder decides. The fee stays due either way.",
  });
  if (!cert || !(feeRelease || correction || revocation || reinstatement)) return null;
  const close = (open: boolean) => {
    if (!open) setDialog(null);
  };
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm" variant="outline" aria-label={`More actions for ${name}`}>
            <MoreHorizontal className="size-4" aria-hidden />
            <span className="hidden sm:inline">More</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {feeRelease && <DropdownMenuItem onSelect={() => setDialog("fee")}>Ask for a fee release</DropdownMenuItem>}
          {correction && <DropdownMenuItem onSelect={() => setDialog("correction")}>Request a correction</DropdownMenuItem>}
          {revocation && <DropdownMenuItem onSelect={() => setDialog("revocation")}>Request revocation</DropdownMenuItem>}
          {reinstatement && <DropdownMenuItem onSelect={() => setDialog("reinstatement")}>Request reinstatement</DropdownMenuItem>}
        </DropdownMenuContent>
      </DropdownMenu>
      {dialog === "fee" && (
        <FormDialog
          open
          onOpenChange={close}
          title={`Ask for a fee release for ${name}`}
          description={`${rupees(row.fee?.balance)} is still to pay. The Founder decides. A release only lets the certificate go ahead; the fee stays due.`}
          submitLabel="Ask for release"
          fields={[{ name: "reason", label: "Why the certificate should go ahead now", kind: "textarea", required: true }]}
          onSubmit={(v) => exception.mutateAsync(v["reason"]!)}
        />
      )}
      {dialog === "correction" && (
        <FormDialog
          open
          onOpenChange={close}
          title="Request a correction"
          description="Another approver decides it, not you. The corrected version keeps the number; the current one stays valid until then."
          submitLabel="Request correction"
          fields={[
            { name: "reason", label: "Reason (for example a name correction)", kind: "textarea", required: true },
            { name: "name", label: "Name to print", kind: "text", initial: name },
          ]}
          onSubmit={(v) => ask.mutateAsync({ kind: "Correction", reason: v["reason"]!, holder_name: v["name"]!.trim() || undefined })}
        />
      )}
      {dialog === "revocation" && (
        <FormDialog
          open
          onOpenChange={close}
          title="Request revocation"
          description="The Founder or Super Admin decides. A revoked certificate no longer verifies as valid, and the page anyone can open shows that."
          submitLabel="Request revocation"
          destructive
          fields={[
            { name: "reason", label: "Reason", kind: "textarea", required: true },
            { name: "evidence", label: "Evidence", kind: "textarea", required: true },
          ]}
          onSubmit={(v) => ask.mutateAsync({ kind: "Revocation", reason: v["reason"]!, evidence: v["evidence"]! })}
        />
      )}
      {dialog === "reinstatement" && (
        <FormDialog
          open
          onOpenChange={close}
          title="Request reinstatement"
          description="For a revocation made by mistake. The Founder or Super Admin decides; the time it was revoked stays on record."
          submitLabel="Request reinstatement"
          fields={[
            { name: "reason", label: "Reason", kind: "textarea", required: true },
            { name: "evidence", label: "Evidence", kind: "textarea", required: true },
          ]}
          onSubmit={(v) => ask.mutateAsync({ kind: "Reinstatement", reason: v["reason"]!, evidence: v["evidence"]! })}
        />
      )}
    </>
  );
}
