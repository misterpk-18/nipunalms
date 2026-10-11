/** Approve and Reject (or Return) side by side with the same weight: neither is chosen for you. Approve confirms with what happens
 * next; Reject always asks for a reason. */
import type { ReactNode } from "react";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Button } from "@/components/ui/button";
import { ReasonDialog } from "@/features/shared/reason-dialog";

export type ApproveSpec = {
  label?: string;
  title: string;
  /** What happens when you approve, in plain words. */
  consequence: string;
  confirmLabel?: string;
  /** Ask for a written basis before approving (the API wants one for some decisions). */
  askFor?: string;
  onApprove: (note?: string) => Promise<unknown>;
};

/** A dialog of its own in place of the plain confirm (the curriculum choice of when to activate, the new end date of an access extension). */
export type CustomApprove = { custom: ReactNode };

export type RejectSpec = {
  label?: string;
  title: string;
  /** What happens when you say no. */
  consequence: string;
  reasonLabel?: string;
  onReject: (reason: string) => Promise<unknown> | unknown;
};

export function ApproveRejectBar({ approve, reject, busy }: { approve: ApproveSpec | CustomApprove; reject: RejectSpec; busy: boolean }) {
  const approveLabel = "custom" in approve ? "Approve" : (approve.label ?? "Approve");
  const approveButton = (
    <Button disabled={busy} className="min-w-28">
      {approveLabel}
    </Button>
  );
  return (
    <>
      <ReasonDialog
        trigger={
          <Button variant="outline" disabled={busy} className="min-w-28 border-destructive/50 text-destructive hover:bg-destructive/10">
            {reject.label ?? "Reject"}
          </Button>
        }
        title={reject.title}
        description={reject.consequence}
        label={reject.reasonLabel ?? "Why are you saying no? (they will read this)"}
        confirmLabel={reject.label ?? "Reject"}
        destructive
        busy={busy}
        minLength={5}
        onSubmit={reject.onReject}
      />
      {"custom" in approve ? (
        approve.custom
      ) : approve.askFor ? (
        <ReasonDialog
          trigger={approveButton}
          title={approve.title}
          description={approve.consequence}
          label={approve.askFor}
          confirmLabel={approve.confirmLabel ?? approveLabel}
          busy={busy}
          minLength={5}
          onSubmit={(note) => approve.onApprove(note)}
        />
      ) : (
        <ConfirmDialog
          title={approve.title}
          consequence={approve.consequence}
          confirmLabel={approve.confirmLabel ?? approveLabel}
          onConfirm={() => approve.onApprove()}
        >
          {approveButton}
        </ConfirmDialog>
      )}
    </>
  );
}
