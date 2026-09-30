/** The Certificate Register table used by students (read only), coordinators, branch managers and the Super Admin. */
import { useState } from "react";
import { CERTIFICATE_STATUSES, certificatesApi, useCertificateRegister, type Certificate } from "@/api/certificates";
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
  const reissue = useApiMutation((v: { id: number; reason: string; name: string }) => certificatesApi.reissue(v.id, v.reason, v.name || undefined), {
    ...opts,
    success: (c) => `Reissued as version ${c.version}.`,
  });
  const revoke = useApiMutation((v: { id: number; reason: string }) => certificatesApi.revoke(v.id, v.reason), { ...opts, success: "Certificate revoked." });
  const id = certificate.certificate_id;

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
      {certificate.actions.includes("reissue") && (
        <FormDialog
          trigger={
            <Button size="sm" variant="outline">
              Reissue
            </Button>
          }
          title="Reissue certificate"
          description="A new version under the same number; this version becomes Superseded and stays on record."
          submitLabel="Reissue"
          fields={[
            { name: "reason", label: "Reason (for example name correction)", kind: "textarea", required: true },
            { name: "name", label: "Name to print", kind: "text", initial: certificate.holder_name },
          ]}
          onSubmit={(v) => reissue.mutateAsync({ id, reason: v["reason"]!, name: v["name"]!.trim() })}
        />
      )}
      {certificate.actions.includes("revoke") && (
        <FormDialog
          trigger={
            <Button size="sm" variant="destructive">
              Revoke
            </Button>
          }
          title="Revoke certificate"
          description="Revocation is audited and shown on public verification."
          submitLabel="Revoke"
          destructive
          fields={[{ name: "reason", label: "Reason", kind: "textarea", required: true }]}
          onSubmit={(v) => revoke.mutateAsync({ id, reason: v["reason"]! })}
        />
      )}
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
