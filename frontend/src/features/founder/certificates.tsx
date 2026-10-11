import { PageHead } from "@/components/lms/ui";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { InboxList } from "./inbox-list";

/** Corrections, revocations, reinstatements and fee releases that wait for the Founder / CEO or Super Admin. */
export function FounderCertificates() {
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead
        title="Certificate decisions"
        description="Decide requests to correct, revoke or reinstate a certificate, and to release one while a fee is unpaid."
      />
      <InboxList page="/founder/certificates" group="certificates" title="Waiting for you" empty="No certificate request is waiting for you." />
      <HowThisWorks>
        <p>
          You never decide a request you made yourself. Approving a revocation shows the certificate as revoked on public verification. Releasing a certificate
          for an unpaid fee does not waive the fee: it stays due in the CRM.
        </p>
      </HowThisWorks>
    </div>
  );
}
