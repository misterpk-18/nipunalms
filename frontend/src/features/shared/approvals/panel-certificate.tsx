/** Certificate decisions: a correction, a revocation or a reinstatement, and a release for an unpaid fee. Approve or Reject, never preselected. */
import { certificatesApi, type CertificateRequest, type FinancialException, type RequestKind } from "@/api/certificates";
import { KeyValue } from "@/components/lms/ui";
import { fmtDateTime } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";
import { ApproveRejectBar } from "./decision-bar";
import { PanelFrame, PanelPart } from "./panel-frame";

const INVALIDATE = [["founder"], ["nav"], ["certificates"], ["completion"]];

/** What each decision does, in plain words (the line under the confirm). */
const APPROVE_LINE: Record<RequestKind, string> = {
  Correction: "A corrected certificate is issued with the same number. The old copy is marked as replaced.",
  Revocation: "The certificate stops being valid. Anyone who checks its number will see that it was revoked. This is recorded in the audit log.",
  Reinstatement: "The certificate becomes valid again with the same number. The time it was revoked stays on record.",
};
const REJECT_LINE: Record<RequestKind, string> = {
  Correction: "The certificate stays as it is. The person who asked is told why.",
  Revocation: "The certificate stays valid. The person who asked is told why.",
  Reinstatement: "The certificate stays revoked. The person who asked is told why.",
};
/** Shown in place of the decision buttons when the API says this person cannot decide the request (they asked for it). */
function IndependenceNote() {
  return (
    <p className="text-sm text-muted-foreground">
      You asked for this, so someone else decides it. Nobody decides their own request; a Branch Manager's request goes to the Founder or a Super Admin.
    </p>
  );
}

const NOUN: Record<RequestKind, string> = { Correction: "correction", Revocation: "revocation", Reinstatement: "reinstatement" };

export function CertificateRequestPanel({
  request,
  fromBranchManager,
  canDecide = true,
  onClose,
}: {
  request: CertificateRequest;
  fromBranchManager: boolean;
  canDecide?: boolean;
  onClose: () => void;
}) {
  const kind = request.kind;
  const number = request.certificate.certificate_number ?? "this certificate";
  const decide = useApiMutation(
    (v: { decision: "Approved" | "Rejected"; note?: string }) => certificatesApi.decideRequest(request.request_id, v.decision, v.note),
    {
      success: (r) => `${r.kind} ${r.status === "Approved" ? "approved" : "rejected"}`,
      next: (r) => (r.status === "Approved" ? `${request.requested_by.full_name} is told.` : `${request.requested_by.full_name} is told, with your reason.`),
      invalidate: INVALIDATE,
      onSuccess: onClose,
    },
  );
  const changes = Object.entries(request.changes).map(([field, v]) => `${field === "holder_name" ? "Name" : field}: ${v.from} to ${v.to}`);
  return (
    <PanelFrame
      open
      onClose={onClose}
      title={`${kind} of certificate ${number}`}
      description={`${request.certificate.holder_name} · ${request.certificate.course.title}`}
      fromBranchManager={fromBranchManager}
      bar={
        !canDecide ? (
          <IndependenceNote />
        ) : (
          <ApproveRejectBar
            busy={decide.isPending}
            approve={{
              title: `Approve the ${NOUN[kind]}?`,
              consequence: APPROVE_LINE[kind],
              onApprove: () => decide.mutateAsync({ decision: "Approved" }),
            }}
            reject={{
              title: `Reject the ${NOUN[kind]}?`,
              consequence: REJECT_LINE[kind],
              onReject: (note) => decide.mutateAsync({ decision: "Rejected", note }),
            }}
          />
        )
      }
    >
      <KeyValue
        items={[
          ["Certificate", `${number} (version ${request.certificate.version})`],
          ["Holder", request.certificate.holder_name],
          ["Branch", request.certificate.branch.branch_name],
          ["Asked by", `${request.requested_by.full_name}, ${fmtDateTime(request.requested_at)}`],
        ]}
      />
      <PanelPart title="Why it was asked for">
        <p className="text-sm">{request.reason}</p>
      </PanelPart>
      {request.evidence && (
        <PanelPart title="Evidence">
          <p className="text-sm">{request.evidence}</p>
        </PanelPart>
      )}
      {changes.length > 0 && (
        <PanelPart title="What would change">
          <ul className="list-disc pl-5 text-sm">
            {changes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </PanelPart>
      )}
    </PanelFrame>
  );
}

export function FeeExceptionPanel({
  exception,
  fromBranchManager,
  canDecide = true,
  onClose,
}: {
  exception: FinancialException;
  fromBranchManager: boolean;
  canDecide?: boolean;
  onClose: () => void;
}) {
  const decide = useApiMutation(
    (v: { decision: "Approved" | "Rejected"; note: string }) => certificatesApi.decideException(exception.exception_id, v.decision, v.note),
    {
      success: (e) => `Release ${e.status === "Approved" ? "approved" : "rejected"}`,
      next: (e) =>
        e.status === "Approved"
          ? `${exception.requested_by.full_name} can now go ahead with the certificate. The unpaid amount stays due in the CRM.`
          : `${exception.requested_by.full_name} is told. The certificate waits until the fee is paid.`,
      invalidate: INVALIDATE,
      onSuccess: onClose,
    },
  );
  const amount = `₹${Number(exception.outstanding_amount).toLocaleString("en-IN")}`;
  return (
    <PanelFrame
      open
      onClose={onClose}
      title={`Release certificates with a fee unpaid`}
      description={`Admission ${exception.admission.admission_code} · ${amount} outstanding`}
      fromBranchManager={fromBranchManager}
      bar={
        !canDecide ? (
          <IndependenceNote />
        ) : (
          <ApproveRejectBar
            busy={decide.isPending}
            approve={{
              title: "Release the certificates?",
              consequence: `The certificate can go ahead although ${amount} is unpaid. The fee is not waived: it stays due in the CRM.`,
              confirmLabel: "Release",
              askFor: "Why are you releasing it? (kept in the audit log)",
              onApprove: (note) => decide.mutateAsync({ decision: "Approved", note: note ?? "" }),
            }}
            reject={{
              title: "Keep the certificates on hold?",
              consequence: "The certificates stay on hold until the fee is paid. The person who asked is told why.",
              label: "Keep on hold",
              onReject: (note) => decide.mutateAsync({ decision: "Rejected", note }),
            }}
          />
        )
      }
    >
      <KeyValue
        items={[
          ["Admission", exception.admission.admission_code],
          ["Still to pay", amount],
          ["Certificates", exception.certificate_types.join(", ")],
          ["Asked by", `${exception.requested_by.full_name}, ${fmtDateTime(exception.requested_at)}`],
        ]}
      />
      <PanelPart title="Why it was asked for">
        <p className="text-sm">{exception.reason}</p>
      </PanelPart>
    </PanelFrame>
  );
}
