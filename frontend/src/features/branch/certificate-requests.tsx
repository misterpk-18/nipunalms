/** Certificate requests: corrections, revocations and fee releases waiting for a decision, and who decides each. */
import { PageHead } from "@/components/lms/ui";
import { ApprovalsInbox } from "@/features/shared/approvals/inbox";

export function BranchCertificateRequests() {
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <PageHead
        title="Certificate requests"
        description="Corrections, revocations, reinstatements and fee releases for certificates, and who decides each. To approve and issue a certificate, use Completion & certificates."
      />
      <ApprovalsInbox
        page="/branch/certificate-requests"
        group="certificates"
        kinds={["certificate"]}
        title="Certificate requests"
        empty="No certificate request is waiting for a decision. New requests appear here."
      />
    </div>
  );
}
