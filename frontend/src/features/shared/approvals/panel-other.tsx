/** The monthly AI budget, and a Branch Manager's own reschedule or attendance request. */
import { useState } from "react";
import { attendanceApi } from "@/api/attendance";
import { deliveryApi } from "@/api/delivery";
import { founderApi, type AiBudgetDetail, type InboxItem } from "@/api/founder";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { Field } from "@/components/lms/forms";
import { KeyValue } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmtDateTime, fmtRange } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { ApproveRejectBar } from "./decision-bar";
import { PanelFrame, PanelPart } from "./panel-frame";

const INVALIDATE = [["founder"], ["nav"], ["delivery"], ["progress"], ["attendance"], ["branch"], ["dashboard"]];

export function AiBudgetPanel({ detail, onClose }: { detail: AiBudgetDetail; onClose: () => void }) {
  const [amount, setAmount] = useState("");
  const rupees = Number(amount);
  const valid = Number.isInteger(rupees) && rupees >= 1;
  const approve = useApiMutation((value: number) => founderApi.approveAiBudget(value), {
    success: "Monthly AI budget approved",
    next: "It now shows on the dashboards.",
    invalidate: [["founder"], ["nav"], ["dashboard"]],
    onSuccess: onClose,
  });
  return (
    <PanelFrame
      open
      onClose={onClose}
      title="Approve the monthly AI budget"
      description="The most Ask Nipuna may cost in a month, in rupees."
      bar={
        <ConfirmDialog
          title={`Approve ₹${valid ? rupees.toLocaleString("en-IN") : "…"} a month?`}
          consequence="This becomes the monthly AI budget shown on the dashboards. It is recorded in the audit log."
          confirmLabel="Approve budget"
          onConfirm={() => approve.mutateAsync(rupees)}
        >
          <Button disabled={!valid || approve.isPending} className="min-w-28">
            Approve budget
          </Button>
        </ConfirmDialog>
      }
    >
      <p className="text-sm text-muted-foreground">
        {detail.state === "Configured"
          ? `The budget is ₹${detail.amount_inr.toLocaleString("en-IN")} a month.`
          : "No budget has been approved yet, so the dashboards say it is waiting for you. Enter the amount after you have the developer's estimate."}
      </p>
      <Field label="Monthly budget (₹)" htmlFor="ai-budget" hint="Whole rupees, for example 25000.">
        <Input id="ai-budget" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d]/g, ""))} />
      </Field>
    </PanelFrame>
  );
}

export function BranchManagerRequestPanel({ item, onClose }: { item: Extract<InboxItem, { kind: "bm_reschedule" | "bm_correction" }>; onClose: () => void }) {
  const reschedule = useApiMutation<{ decision: "approve" | "reject"; note?: string }, unknown>(
    (v) =>
      item.kind === "bm_reschedule"
        ? v.decision === "approve"
          ? deliveryApi.approveRequest(item.detail.request_id, v.note ? { note: v.note } : {})
          : deliveryApi.rejectRequest(item.detail.request_id, v.note ?? "")
        : attendanceApi.decideCorrection(item.detail.correction_id, {
            decision: v.decision === "approve" ? "Approved" : "Rejected",
            ...(v.note ? { decision_note: v.note } : {}),
          }),
    {
      success: (_r) => "Decision recorded",
      next: `${item.detail.requested_by.full_name} is told.`,
      invalidate: INVALIDATE,
      onSuccess: onClose,
    },
  );
  const who = item.detail.requested_by.full_name;
  const d = item.detail;
  const isReschedule = item.kind === "bm_reschedule";
  const approveLine = isReschedule
    ? "The class moves to the new time. The trainer and the students are told."
    : "The register entry changes. Who approved it is recorded, and the old value stays in the audit log.";
  return (
    <PanelFrame
      open
      onClose={onClose}
      title={item.title}
      description={item.where ?? undefined}
      fromBranchManager
      bar={
        <ApproveRejectBar
          busy={reschedule.isPending}
          approve={{
            title: isReschedule ? "Move the class?" : "Change the attendance entry?",
            consequence: approveLine,
            onApprove: () => reschedule.mutateAsync({ decision: "approve" }),
          }}
          reject={{
            title: "Say no to this request?",
            consequence: `${who} is told, with your reason. Nothing changes.`,
            onReject: (note) => reschedule.mutateAsync({ decision: "reject", note }),
          }}
        />
      }
    >
      {"proposed_starts_at" in d ? (
        <KeyValue
          items={[
            ["Class", `${d.session.title} (${d.session.batch.batch_code})`],
            ["Now", fmtRange(d.session.starts_at, d.session.ends_at)],
            ["Asked to move to", `${fmtDateTime(d.proposed_starts_at)} to ${fmtRange(d.proposed_starts_at, d.proposed_ends_at).split("–")[1]}`],
            ["Asked by", who],
          ]}
        />
      ) : (
        <KeyValue
          items={[
            ["Student", `${d.student.full_name} (${d.student.student_code})`],
            ["Class", d.session.title],
            ["The register says", d.previous_status ?? "Not marked"],
            ["Asked to change to", d.requested_status],
            ["Asked by", `${who}, ${fmtDateTime(d.requested_at)}`],
          ]}
        />
      )}
      <PanelPart title="Why">
        <p className="text-sm">{d.reason}</p>
      </PanelPart>
    </PanelFrame>
  );
}
