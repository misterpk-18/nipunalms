/** Approvals: everything waiting for a decision, in the one inbox. The Super Admin decides every item here, like the Founder does on Home. */
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead } from "@/components/lms/ui";
import type { InboxKind } from "@/api/founder";
import { ApprovalsInbox } from "./inbox";

/** What the Approvals page lists: certificate requests and fee releases, access extensions, the AI budget and Branch Managers' own requests. */
const KINDS: InboxKind[] = ["certificate", "fee_exception", "access_extension", "ai_budget", "bm_reschedule", "bm_correction"];

export function ApprovalsPage({ page }: { page: string }) {
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead
        title="Approvals"
        description="Decide what is waiting: certificate corrections, revocations and fee releases, access extensions beyond a Branch Manager's limit, the AI budget, and a Branch Manager's own requests."
      />
      <ApprovalsInbox page={page} kinds={KINDS} title="Waiting for you" empty="Nothing is waiting for you. New items appear here as they come in." />
      <HowThisWorks>
        <p>
          You never decide a request you made yourself; it is listed so you can read it, and the Founder or a Super Admin decides it. A Branch Manager's own
          request comes here because nobody at the branch can review it independently.
        </p>
        <p>
          Approving a revocation shows the certificate as revoked on public verification. Releasing a certificate for an unpaid fee does not waive the fee: it
          stays due in the CRM.
        </p>
      </HowThisWorks>
    </div>
  );
}
