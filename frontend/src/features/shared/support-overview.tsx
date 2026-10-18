/** Student support for the Super Admin and Founder: every branch (branch filter), read and reassign. Replies and decisions stay with the branch. */
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead } from "@/components/lms/ui";
import { useUrlParams } from "@/features/admin/url-params";
import { SupportDesk } from "@/features/shared/support-desk";

export function SupportOverview() {
  const [params, setParams] = useUrlParams();
  const request = Number(params["request"]) > 0 ? Number(params["request"]) : null;
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Student support"
        description="Requests students have raised in every branch. You can read each one and hand it to the right person; the branch replies to the student."
      />
      <SupportDesk
        views
        branchFilter
        canReassign
        canEscalate={false}
        canRespond={false}
        caption="Support requests"
        empty="No support requests."
        openId={request}
        onOpen={(id) => setParams({ request: id === null ? undefined : String(id) })}
      />
      <HowThisWorks>
        <p>Pick a branch to see only its requests. Open a request to read the conversation and, under Reassign to, give it to another person at that branch.</p>
        <p>Access extensions beyond a Branch Manager's limit are decided in Approvals.</p>
      </HowThisWorks>
    </div>
  );
}
