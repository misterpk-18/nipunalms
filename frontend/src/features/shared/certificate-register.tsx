/** The Certificate Register table used by students (read only), coordinators, branch managers and the Super Admin, and the
 * decisions that need an independent approver: change requests (correction, revocation, reinstatement) and fee exceptions. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CERTIFICATE_STATUSES,
  certificatesApi,
  useCertificateRegister,
  type Certificate,
  type CertificateRequest,
  type FinancialException,
} from "@/api/certificates";
import { NativeSelect } from "@/components/lms/forms";
import { DataTable, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormDialog } from "@/features/shared/attendance-parts";
import { fmtDate } from "@/features/shared/format";
import { useApiMutation } from "@/lib/mutation";

const REGISTER_KEYS = [["certificates"], ["completion"]];

export function CertificateActions({ certificate }: { certificate: Certificate }) {
  const opts = { invalidate: REGISTER_KEYS };
  const recommend = useApiMutation((id: number) => certificatesApi.recommend(id), { ...opts, success: "Recommended for approval." });
  const approve = useApiMutation((id: number) => certificatesApi.approve(id), { ...opts, success: "Approved for issue." });
  const issue = useApiMutation((id: number) => certificatesApi.issue(id), { ...opts, success: (c) => `Issued as ${c.certificate_number}.` });
  const back = useApiMutation((v: { id: number; reason: string }) => certificatesApi.returnToReview(v.id, v.reason), {
    ...opts,
    success: "Returned for review.",
  });
  const ask = useApiMutation(
    (v: { id: number; body: Parameters<typeof certificatesApi.requestChange>[1] }) => certificatesApi.requestChange(v.id, v.body),
    { ...opts, success: (r) => `${r.kind} requested; an independent approver decides it.` },
  );
  const exception = useApiMutation((v: { id: number; reason: string }) => certificatesApi.requestException(v.id, v.reason), {
    ...opts,
    success: "Exception requested; the Founder / CEO or Super Admin decides it.",
  });
  const id = certificate.certificate_id;
  const fee = certificate.fee_clearance;
  const feeHeld = fee && !fee.cleared && (certificate.status === "Eligibility Review" || certificate.status === "Approved for Issue");

  return (
    <div className="flex flex-wrap gap-2">
      {certificate.actions.includes("recommend") && (
        <Button size="sm" variant="outline" disabled={recommend.isPending} onClick={() => recommend.mutate(id)}>
          Recommend
        </Button>
      )}
      {certificate.actions.includes("approve") && (
        <Button size="sm" disabled={approve.isPending} onClick={() => approve.mutate(id)}>
          Approve for issue
        </Button>
      )}
      {certificate.actions.includes("return") && (
        <FormDialog
          trigger={
            <Button size="sm" variant="ghost">
              Return
            </Button>
          }
          title="Return for review"
          submitLabel="Return"
          fields={[{ name: "reason", label: "What needs another look?", kind: "textarea", required: true }]}
          onSubmit={(v) => back.mutateAsync({ id, reason: v["reason"]! })}
        />
      )}
      {certificate.actions.includes("issue") && (
        <Button size="sm" disabled={issue.isPending} onClick={() => issue.mutate(id)}>
          Issue
        </Button>
      )}
      {feeHeld && fee.state === "Outstanding" && (
        <FormDialog
          trigger={
            <Button size="sm" variant="outline">
              Request fee exception
            </Button>
          }
          title="Request a certificate release exception"
          description={`₹${fee.balance} is outstanding. The Founder / CEO or Super Admin decides; the debt stays due in the CRM.`}
          submitLabel="Request"
          fields={[{ name: "reason", label: "Why the certificate should go ahead now", kind: "textarea", required: true }]}
          onSubmit={(v) => exception.mutateAsync({ id, reason: v["reason"]! })}
        />
      )}
      {certificate.actions.includes("request_correction") && (
        <FormDialog
          trigger={
            <Button size="sm" variant="outline">
              Request correction
            </Button>
          }
          title="Request a correction"
          description="Approved by the Branch Manager or Super Admin (not you). The new version keeps the number; this one stays valid until then."
          submitLabel="Request"
          fields={[
            { name: "reason", label: "Reason (for example name correction)", kind: "textarea", required: true },
            { name: "name", label: "Name to print", kind: "text", initial: certificate.holder_name },
          ]}
          onSubmit={(v) =>
            ask.mutateAsync({ id, body: { kind: "Correction", reason: v["reason"]!, holder_name: v["name"]!.trim() || undefined } })
          }
        />
      )}
      {certificate.actions.includes("request_revocation") && (
        <FormDialog
          trigger={
            <Button size="sm" variant="destructive">
              Request revocation
            </Button>
          }
          title="Request revocation"
          description="Decided by the Founder / CEO or Super Admin (not you). Revocation is audited and shown on public verification."
          submitLabel="Request"
          destructive
          fields={[
            { name: "reason", label: "Reason", kind: "textarea", required: true },
            { name: "evidence", label: "Evidence", kind: "textarea", required: true },
          ]}
          onSubmit={(v) => ask.mutateAsync({ id, body: { kind: "Revocation", reason: v["reason"]!, evidence: v["evidence"]! } })}
        />
      )}
      {certificate.actions.includes("request_reinstatement") && (
        <FormDialog
          trigger={
            <Button size="sm" variant="outline">
              Request reinstatement
            </Button>
          }
          title="Request reinstatement"
          description="For a mistaken revocation. Decided by the Founder / CEO or Super Admin; the revoked interval stays on record."
          submitLabel="Request"
          fields={[
            { name: "reason", label: "Reason", kind: "textarea", required: true },
            { name: "evidence", label: "Evidence", kind: "textarea", required: true },
          ]}
          onSubmit={(v) => ask.mutateAsync({ id, body: { kind: "Reinstatement", reason: v["reason"]!, evidence: v["evidence"]! } })}
        />
      )}
      {certificate.pending_request && <StatusBadge>{`${certificate.pending_request.kind} requested`}</StatusBadge>}
    </div>
  );
}

export function CertificateTable({ rows, withActions = true }: { rows: Certificate[]; withActions?: boolean }) {
  return (
    <DataTable
      caption="Certificate Register"
      rows={rows}
      getKey={(c) => c.certificate_id}
      empty="No certificate register entries."
      cols={[
        { h: "Number", c: (c) => c.certificate_number ?? "—" },
        { h: "Type", c: (c) => c.certificate_type },
        { h: "Course", c: (c) => `${c.course.course_code} ${c.course.title}` },
        { h: "Holder", c: (c) => `${c.holder_name} (${c.branch.branch_code.replace("NIT-", "")})` },
        { h: "Status", c: (c) => <StatusBadge>{c.status}</StatusBadge> },
        ...(withActions ? [{ h: "Fee", c: (c: Certificate) => feeLabel(c) }] : []),
        {
          h: "Version",
          c: (c) =>
            c.reason && c.version > 1
              ? `${c.version_label} — ${c.reason}`
              : c.status === "Revoked" && c.reason
                ? `${c.version_label} — ${c.reason}`
                : c.version_label,
        },
        ...(withActions ? [{ h: "Action", c: (c: Certificate) => <CertificateActions certificate={c} /> }] : []),
      ]}
    />
  );
}

function feeLabel(c: Certificate) {
  const fee = c.fee_clearance;
  if (!fee) return "—";
  return fee.state === "Outstanding" ? `Outstanding ₹${fee.balance}` : fee.state;
}

/** Change requests and fee exceptions waiting for the signed-in approver, with the recent decisions. */
export function CertificateDecisions() {
  const requests = useQuery({ queryKey: ["certificates", "requests"], queryFn: () => certificatesApi.requests({ status: "Pending", per_page: 100 }) });
  const exceptions = useQuery({
    queryKey: ["certificates", "exceptions"],
    queryFn: () => certificatesApi.exceptions({ status: "Pending", per_page: 100 }),
  });
  const opts = { invalidate: REGISTER_KEYS };
  const decideRequest = useApiMutation(
    (v: { id: number; decision: "Approved" | "Rejected"; note?: string }) => certificatesApi.decideRequest(v.id, v.decision, v.note),
    { ...opts, success: (r) => `${r.kind} ${r.status.toLowerCase()}.` },
  );
  const decideException = useApiMutation(
    (v: { id: number; decision: "Approved" | "Rejected"; note: string }) => certificatesApi.decideException(v.id, v.decision, v.note),
    { ...opts, success: (e) => `Exception ${e.status.toLowerCase()}.` },
  );
  const decisionFields = [
    { name: "decision", label: "Decision", kind: "select" as const, options: ["Approved", "Rejected"], required: true, initial: "Approved" },
    { name: "note", label: "Note (required to reject)", kind: "textarea" as const },
  ];
  return (
    <div className="space-y-4">
      <QueryView query={requests} isEmpty={(p) => p.data.length === 0} empty="No certificate request is waiting for a decision.">
        {(page) => (
          <DataTable
            caption="Certificate requests waiting for a decision"
            rows={page.data}
            getKey={(r: CertificateRequest) => r.request_id}
            cols={[
              { h: "Certificate", c: (r) => `${r.certificate.certificate_number ?? "—"} v${r.certificate.version} · ${r.certificate.holder_name}` },
              { h: "Request", c: (r) => <StatusBadge>{r.kind}</StatusBadge> },
              {
                h: "Reason",
                c: (r) =>
                  [r.reason, r.evidence && `Evidence: ${r.evidence}`, ...Object.entries(r.changes).map(([k, v]) => `${k}: ${v.from} → ${v.to}`)]
                    .filter(Boolean)
                    .join(" · "),
              },
              { h: "Asked by", c: (r) => `${r.requested_by.full_name}, ${fmtDate(r.requested_at)}` },
              {
                h: "Decision",
                c: (r) =>
                  r.actions.includes("decide") ? (
                    <FormDialog
                      trigger={<Button size="sm">Decide</Button>}
                      title={`${r.kind} of ${r.certificate.certificate_number}`}
                      submitLabel="Record decision"
                      fields={decisionFields}
                      onSubmit={(v) =>
                        decideRequest.mutateAsync({ id: r.request_id, decision: v["decision"] as "Approved" | "Rejected", note: v["note"] || undefined })
                      }
                    />
                  ) : (
                    "Another approver decides"
                  ),
              },
            ]}
          />
        )}
      </QueryView>
      <QueryView query={exceptions} isEmpty={(p) => p.data.length === 0} empty="No fee exception is waiting for a decision.">
        {(page) => (
          <DataTable
            caption="Certificate release exceptions (unpaid fee) waiting for a decision"
            rows={page.data}
            getKey={(e: FinancialException) => e.exception_id}
            cols={[
              { h: "Admission", c: (e) => e.admission.admission_code },
              { h: "Outstanding", c: (e) => `₹${e.outstanding_amount}` },
              { h: "Certificates", c: (e) => e.certificate_types.join(", ") },
              { h: "Reason", c: (e) => e.reason },
              { h: "Asked by", c: (e) => `${e.requested_by.full_name}, ${fmtDate(e.requested_at)}` },
              {
                h: "Decision",
                c: (e) =>
                  e.actions.includes("decide") ? (
                    <FormDialog
                      trigger={<Button size="sm">Decide</Button>}
                      title={`Release exception for ${e.admission.admission_code}`}
                      description="Approving lets the certificate go ahead; the debt is not waived."
                      submitLabel="Record decision"
                      fields={[decisionFields[0]!, { name: "note", label: "Basis of the decision", kind: "textarea" as const, required: true }]}
                      onSubmit={(v) =>
                        decideException.mutateAsync({ id: e.exception_id, decision: v["decision"] as "Approved" | "Rejected", note: v["note"]! })
                      }
                    />
                  ) : (
                    "The Founder / CEO or Super Admin decides"
                  ),
              },
            ]}
          />
        )}
      </QueryView>
    </div>
  );
}

/** Filterable register for staff screens. */
export function CertificateRegister({ branchId }: { branchId?: number }) {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const query = useCertificateRegister({ status, q, branch_id: branchId, per_page: 100 });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <NativeSelect
          aria-label="Status"
          className="w-56"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          placeholder="All statuses"
          options={CERTIFICATE_STATUSES.map((s) => ({ value: s, label: s }))}
        />
        <Input aria-label="Search" className="w-64" placeholder="Search holder, Student ID or number" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <QueryView query={query}>{(page) => <CertificateTable rows={page.data} />}</QueryView>
    </div>
  );
}
